"""Frozen092 ORDER/BAG 181-head target transfer. Exact root actual authorization only.

Accepted071 owns mature training/weights. Old024 is referenced only for the
fixed random map and canonical tuple BAG. No old fit, target, mask or report runs.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
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


def _module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


alignment_ref=_module('stage094_alignment093',TOOLS/'stage093_sequence_alignment.py')
legacy=alignment_ref.legacy
information_ref=_module('stage094_pure086',TOOLS/'stage086_oi_fit.py')
rff_ref=_module('stage094_pure024',TOOLS/'stage024_ordered_history_experiment.py')
PROTOCOL=alignment_ref.PROTOCOL
PROTOCOL_SHA=alignment_ref.PROTOCOL_SHA
STAGE_ROOT=LINE/'outputs/stage094_crossday_order_fit'
COMMON=legacy.COMMON
IDENTITY=legacy.IDENTITY
LABEL_COLUMNS=list(dict.fromkeys(legacy.LABEL_COLUMNS+['participation_state']))
ARMS=('ORDER','BAG')
SCOPES=('main','holdout_0','holdout_1')
CUTOFFS=('2020-01-01','2023-01-01')
PARAMETERS=dict(alpha=1.,fit_intercept=True,solver='cholesky')
FEATURE_NAMES=COMMON+[c+'_missing' for c in COMMON]+['sequence_missing']+[f'rff_{i:03d}' for i in range(128)]
INPUT_ROLES={'common_npz','common_identity','narrow_labels','narrow_manifest','prepare_manifest','alignment','prepare_terminal','tensor'}
file_binding=legacy.file_binding
read_bound=legacy.read_bound
same_binding=legacy.same_binding
write_json=legacy.write_json
write_csv=legacy.write_csv
write_npz=legacy.write_npz
make_mapping=rff_ref.make_mapping


def source_bundle():
    names=('stage094_crossday_order_fit.py','test_stage094_crossday_order_fit.py','stage093_sequence_alignment.py',
        'stage071_settlement_narrow_fit.py','stage086_oi_fit.py','stage024_ordered_history_experiment.py')
    return sorted([file_binding(TOOLS/n) for n in names],key=lambda b:b['path'])


def fit_scalers(common,tensor_index,tensor,weights):
    x,idx,w=np.asarray(common,float),np.asarray(tensor_index,int),np.asarray(weights,float)
    if x.shape!=(len(w),26) or idx.shape!=w.shape or not len(w) or not np.isfinite(w).all() or (w<=0).any():
        raise ValueError('invalid mature scaler inputs')
    if (idx < -1).any() or (idx>=len(tensor)).any():raise ValueError('tensor index outside accepted X')
    common_stats=[legacy.finite_stats(x[:,j],w) for j in range(26)]
    observed=idx>=0
    if observed.any():
        q=tensor[idx[observed]].astype(np.float64)
        if q.shape!=(int(observed.sum()),20,4) or not np.isfinite(q).all():raise ValueError('observed tensor is not finite20x4')
        pooled_weights=np.repeat(w[observed]/20.,20)
        channel_stats=[]
        for j in range(4):
            values=q[:,:,j].reshape(-1)
            # Exact equality on accepted float32 values: no near-zero epsilon.
            if np.equal(values,values[0]).all():
                stat=dict(mean=float(values[0]),var=0.,scale=1.,finite_count=len(values))
            else:stat=legacy.finite_stats(values,pooled_weights)
            channel_stats.append(stat)
    else:
        channel_stats=[dict(mean=0.,var=0.,scale=1.,finite_count=0) for _ in range(4)]
    return dict(common=dict(columns=COMMON,**{k:[s[k] for s in common_stats] for k in ('mean','var','scale','finite_count')}),
        sequence=dict(**{k:[s[k] for s in channel_stats] for k in ('mean','var','scale','finite_count')},
            observed_events=int(observed.sum()),observed_weight_sum=float(w[observed].sum()),
            weighting='observable_current_mature_train_event_weight_divided_by20; all_positions_pooled'),
        feature_names=FEATURE_NAMES,background_dimension=53,head_dimension=181,
        tensor_normalizer='accepted_simple20TR_mean_ATR_not_Wilder',
        missing='raw_channel_train_mean_equals_standardized80zero; shared_sequence_missing; no_gate')


def prepare_fold(frame,common,alignment,tensor,cutoff,next_cutoff,scope):
    a=alignment_ref.validate_alignment(frame,alignment,len(tensor))
    train,prediction=information_ref.fold_slices(frame,cutoff,next_cutoff,scope)
    ti=train.sequence_index.to_numpy(int);pi=prediction.sequence_index.to_numpy(int)
    x=np.asarray(common,float)
    if x.shape!=(len(frame),26):raise ValueError('common26 mother shape differs')
    weights=legacy.training_weights(train);w=weights.sample_weight.to_numpy(float)
    idx=a.legacy_tensor_index.to_numpy(int)
    scaler=fit_scalers(x[ti],idx[ti],tensor,w);scaler.update(scope=scope,cutoff=cutoff)
    return dict(train=train,prediction=prediction,weights=weights,scaler=scaler,
        train_base=legacy.design_base(x[ti],idx[ti]>=0,scaler),prediction_base=legacy.design_base(x[pi],idx[pi]>=0,scaler),
        train_tensor_index=idx[ti],prediction_tensor_index=idx[pi])


def head(background,tensor_index,tensor,arm,scaler,mapping):
    if arm not in ARMS:raise ValueError('unknown fixed layout arm')
    base=np.asarray(background,float);idx=np.asarray(tensor_index,int)
    if base.shape!=(len(idx),53) or not np.isfinite(base).all() or (idx < -1).any() or (idx>=len(tensor)).any():
        raise ValueError('invalid background/tensor index')
    # Missing rows stay standardized zero; raw zero is never normalized as data.
    block=np.zeros((len(idx),20,4),dtype=np.float64);observed=idx>=0
    if observed.any():
        q=tensor[idx[observed]]
        if arm=='BAG':q=rff_ref.canonical_bag(q)
        block[observed]=(q.astype(np.float64)-np.asarray(scaler['sequence']['mean']))/np.asarray(scaler['sequence']['scale'])
    z=np.column_stack([base[:,:11],block.reshape(len(idx),80)])
    W,b=np.asarray(mapping['W_base']),np.asarray(mapping['b'])
    if W.shape!=(91,128) or b.shape!=(128,):raise ValueError('frozen91x128 mapping shape differs')
    phi=np.sqrt(2/128)*np.cos(z@(W/np.sqrt(91))+b)
    result=np.column_stack([base,phi])
    if result.shape!=(len(idx),181) or not np.isfinite(result).all():raise ValueError('nonfinite or non181 head')
    return result


def fit_cell(frame,common,alignment,tensor,cutoff,next_cutoff,scope,directory,mapping,on_fit=None,on_completed=None):
    prepared=prepare_fold(frame,common,alignment,tensor,cutoff,next_cutoff,scope)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    train,prediction=prepared['train'],prepared['prediction'];weights=prepared['weights']
    w=weights.sample_weight.to_numpy(float);y=train.net_R_stress.to_numpy(float)
    write_json(directory/'scaler.json',prepared['scaler'])
    training=train[LABEL_COLUMNS].copy()
    for col in weights:training[col]=weights[col].to_numpy()
    training['legacy_tensor_index']=prepared['train_tensor_index']
    training['sequence_missing']=(prepared['train_tensor_index']<0).astype(np.int8)
    training_binding=write_csv(directory/'training_identity_weights.csv.gz',training)
    pred_identity=prediction[IDENTITY+['label_history_ready20']].copy()
    pred_identity['legacy_tensor_index']=prepared['prediction_tensor_index']
    prediction_binding=write_csv(directory/'prediction_identity.csv.gz',pred_identity)
    identity_sha=hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()
    results=[];records=[]
    for arm in ARMS:
        target=directory/arm;target.mkdir()
        x=head(prepared['train_base'],prepared['train_tensor_index'],tensor,arm,prepared['scaler'],mapping)
        xt=head(prepared['prediction_base'],prepared['prediction_tensor_index'],tensor,arm,prepared['scaler'],mapping)
        estimator=legacy.Ridge(**PARAMETERS)
        if on_fit is not None:on_fit(scope,cutoff,arm)
        with legacy.threadpool_limits(limits=1):estimator.fit(x,y,sample_weight=w)
        if on_completed is not None:on_completed(scope,cutoff,arm)
        scores=estimator.predict(xt)
        portable=dict(schema='stage094_portable_ridge_v1',scope=scope,arm=arm,policy='NARROW',cutoff=cutoff,
            parameters=PARAMETERS,feature_names=FEATURE_NAMES,coef=estimator.coef_.tolist(),intercept=float(estimator.intercept_),
            reconstruction='bound_common_X/alignment/tensor + fold_scaler + shared_mapping; no_saved181_head_cache')
        write_json(target/'portable_model.json',portable)
        with (target/'model.joblib').open('xb') as stream:legacy.joblib.dump(estimator,stream,compress=3)
        z=np.column_stack([x,np.ones(len(x))]);lhs=z.T@(w[:,None]*z)
        lhs[np.arange(181),np.arange(181)]+=1.;rhs=z.T@(w*y)
        beta=np.r_[estimator.coef_,estimator.intercept_]
        if not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):raise ValueError('181 normal equations differ')
        ne=write_npz(target/'normal_equations.npz',lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,weight_sum=np.array(w.sum()))
        if not np.allclose(scores,xt@np.asarray(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):
            raise ValueError('portable181 predictions differ')
        p=legacy.prediction_frame(prediction,scores,'NARROW',arm,cutoff);p['scope']=scope
        p['sequence_missing']=(prepared['prediction_tensor_index']<0).astype(np.int8);results.append(p)
        records.append(dict(scope=scope,arm=arm,policy='NARROW',cutoff=cutoff,dimension=181,target='net_R_stress',
            training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),
            training_sequence_missing=int(training.sequence_missing.sum()),prediction_rows=len(p),prediction_sequence_missing=int(p.sequence_missing.sum()),
            selected=int(p.selected.sum()),training_identity_sha256=identity_sha,max_u_date=str(train.u_date.max()),
            max_label_known_date=str(train.label_known_date.max()),training_identity_weights=training_binding,prediction_identity=prediction_binding,
            scaler=file_binding(directory/'scaler.json'),portable_model=file_binding(target/'portable_model.json'),model=file_binding(target/'model.joblib'),
            normal_equations=ne,normal_equation_max_abs_residual=float(np.max(np.abs(lhs@beta-rhs))),
            full_head_cache_saved=False))
    return pd.concat(results,ignore_index=True),records


def held_diagnostics(predictions,labels):
    adapter=predictions.rename(columns={'sequence_missing':'oi_missing'}).copy()
    adapter['arm']=adapter.arm.map({'ORDER':'OI','BAG':'CONTROL'})
    report,daily,linked=information_ref.held_diagnostics(adapter,labels)
    report.update(schema='stage094_held_closed_diagnostic_v1',contrast='ORDER_minus_BAG',shared_missing='sequence_missing')
    linked=linked.rename(columns={'oi_missing':'sequence_missing'});linked['arm']=linked.arm.map({'OI':'ORDER','CONTROL':'BAG'})
    return report,daily,linked


def opportunity_metrics(predictions,labels):
    report=information_ref.opportunity_metrics(predictions.rename(columns={'sequence_missing':'oi_missing'}),labels)
    report['schema']='stage094_opportunity_metrics_v1'
    for section in ('overall','annual','family_year'):
        for row in report[section]:row['sequence_missing']=row.pop('oi_missing')
    return report


def _csv(binding,columns=None):
    return pd.read_csv(io.BytesIO(read_bound(binding)),compression='gzip',usecols=columns,dtype=str,keep_default_na=False)


def load_inputs(inputs,protocol):
    for role,binding in protocol['input_roles'].items():
        if not same_binding(inputs[role],binding):raise ValueError('fixed current input differs: '+role)
    if not same_binding(inputs['tensor'],protocol['tensor']):raise ValueError('accepted tensor binding differs')
    narrow=json.loads(read_bound(inputs['narrow_manifest']))
    if narrow.get('status')!='completed' or narrow.get('schema')!='stage070_narrow_labels_v1' or not same_binding(narrow.get('labels_narrow',{}),inputs['narrow_labels']):
        raise ValueError('accepted NARROW labels differ')
    frame=legacy.validate_labels(_csv(inputs['narrow_labels'],LABEL_COLUMNS),'NARROW')
    prepare=json.loads(read_bound(inputs['prepare_manifest']));terminal=json.loads(read_bound(inputs['prepare_terminal']))
    if (prepare.get('schema')!='stage093_sequence_alignment_v1' or prepare.get('status')!='completed' or prepare.get('mode')!='actual'
            or prepare.get('protocol',{}).get('sha256')!=PROTOCOL_SHA or prepare.get('mother_rows')!=399252 or prepare.get('legacy_tensor_rows')!=194709
            or not same_binding(prepare.get('alignment',{}),inputs['alignment']) or not same_binding(prepare.get('terminal',{}),inputs['prepare_terminal'])
            or not same_binding(prepare.get('input_bindings',{}).get('narrow_labels',{}),inputs['narrow_labels'])
            or not same_binding(prepare.get('input_bindings',{}).get('old_event_ids',{}),protocol['old_event_ids'])):
        raise ValueError('completed pure-ID preparation differs')
    required=dict(status='completed',completed=True,exit_code=0,completed_projection_rows=399252,
        native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0)
    if any(terminal.get(k)!=v for k,v in required.items()):raise ValueError('prepare terminal differs')
    order_sha=hashlib.sha256(('\n'.join(frame.event_id)+'\n').encode()).hexdigest()
    if prepare.get('full_mother_order_sha256')!=order_sha:raise ValueError('prepare full mother order differs')
    identity=json.loads(read_bound(inputs['common_identity']))
    if (identity.get('rows')!=399252 or identity.get('columns')!=COMMON or identity.get('event_ids_sha256')!=order_sha
            or not same_binding(identity.get('common',{}),inputs['common_npz'])):raise ValueError('common26 identity differs')
    with np.load(io.BytesIO(read_bound(inputs['common_npz'])),allow_pickle=False) as saved:
        if saved['columns'].tolist()!=COMMON or saved['common'].shape!=(399252,26):raise ValueError('common26 schema differs')
        common=saved['common'].astype(np.float64)
    alignment=alignment_ref._integers(_csv(inputs['alignment']),['sequence_index','u_index','legacy_tensor_index','sequence_missing'])
    alignment=alignment_ref.validate_alignment(frame,alignment,194709)
    with np.load(io.BytesIO(read_bound(inputs['tensor'])),allow_pickle=False) as saved:
        if saved.files!=['ordered']:raise ValueError('accepted pure-X tensor keys differ')
        tensor=saved['ordered']
        if tensor.shape!=(194709,20,4) or tensor.dtype.str!='<f4':
            raise ValueError('accepted pure-X tensor schema differs')
    return frame,common,alignment,tensor


def authorize(args):
    out=Path(args.output).resolve()
    if STAGE_ROOT.resolve() not in out.parents:raise ValueError('output outside Stage094 root')
    if out.exists():raise FileExistsError('fresh output required; no automatic retry')
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:raise ValueError('frozen092 protocol required')
    protocol=json.loads(PROTOCOL.read_bytes())
    if not same_binding(file_binding(TOOLS/'stage024_ordered_history_experiment.py'),protocol['pure_functions_reference']):
        raise ValueError('frozen024 pure mapping/canonical BAG source differs')
    binding=file_binding(args.authorization)
    if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(read_bound(binding));required=dict(schema='stage092_exact_root_authorization_v1',authorized_by='root',stage='fit',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root094 authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('exact fit source/test bindings differ')
    if set(auth.get('input_bindings',{}))!=INPUT_ROLES:raise ValueError('fit input roles differ')
    return out,protocol,auth,binding


def run_actual(out,protocol,auth,authorization_binding):
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle();attempted=completed=0
    write_json(out/'actual_started.json',dict(status='started',stage='fit',started_at=datetime.now(timezone.utc).isoformat(),
        source_bundle=bundle,protocol=file_binding(PROTOCOL),authorization=authorization_binding,fixture=False))
    write_json(out/'input_bindings.json',auth['input_bindings'])
    def on_fit(scope,cutoff,arm):
        nonlocal attempted
        attempted+=1
        with (out/'fit_attempts.jsonl').open('a') as stream:stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,arm=arm,attempt=attempted))+'\n');stream.flush()
    def on_completed(scope,cutoff,arm):
        nonlocal completed
        completed+=1
        with (out/'fit_completed.jsonl').open('a') as stream:stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,arm=arm,completed=completed))+'\n');stream.flush()
    try:
        frame,common,alignment,tensor=load_inputs(auth['input_bindings'],protocol)
        mapping=make_mapping();mapping_binding=write_npz(out/'rff_mapping.npz',**mapping)
        predictions=[];records=[]
        for scope in SCOPES:
            for i,cutoff in enumerate(CUTOFFS):
                p,r=fit_cell(frame,common,alignment,tensor,cutoff,CUTOFFS[i+1] if i+1<len(CUTOFFS) else None,scope,
                    out/'folds'/scope/cutoff,mapping,on_fit=on_fit,on_completed=on_completed)
                predictions.append(p);records.extend(r)
                print(json.dumps(dict(phase='fit_cell_complete',scope=scope,cutoff=cutoff,completed=completed)),flush=True)
        predictions=pd.concat(predictions,ignore_index=True)
        main=predictions.loc[predictions.scope.eq('main')].copy();held=predictions.loc[predictions.scope.ne('main')].copy()
        expected=set(frame.loc[frame.u_date.ge(CUTOFFS[0]),'event_id'])
        for name,p in (('main',main),('held_combined',held)):
            if len(p)!=161014*2 or p.duplicated(['event_id','arm']).any() or set(p.arm)!=set(ARMS):raise ValueError('complete forward scores differ: '+name)
            for arm in ARMS:
                if set(p.loc[p.arm.eq(arm),'event_id'])!=expected:raise ValueError('full mother shrunk: '+name)
        if attempted!=12 or completed!=12:raise ValueError('fixed12 fit budget differs')
        h,hd,hl=held_diagnostics(held,frame)
        all_binding=write_csv(out/'predictions.csv.gz',predictions);main_binding=write_csv(out/'predictions_main.csv.gz',main)
        held_binding=write_csv(out/'predictions_holdout.csv.gz',held)
        write_json(out/'held_diagnostic.json',h);hd_binding=write_csv(out/'held_daily.csv.gz',hd);hl_binding=write_csv(out/'held_score_linkage.csv.gz',hl)
        write_json(out/'opportunity_metrics.json',opportunity_metrics(predictions,frame));write_json(out/'fit_records.json',records)
        write_json(out/'summary.json',dict(schema='stage094_fit_summary_v1',actual_fit_calls_completed=completed,prediction_rows=len(predictions),
            main_rows_per_arm=161014,held_combined_rows_per_arm=161014,head_dimension=181,old_head_dimension=139,
            mother_rows=len(frame),mother_label_states=frame.label_state.value_counts().to_dict(),sequence_missing=int(alignment.sequence_missing.sum()),
            full_head_cache_saved=False,strict_pit_claim=False,goal_complete=False,runtime=dict(python=sys.version,sklearn=legacy.sklearn.__version__)))
        if source_bundle()!=bundle:raise ValueError('source changed during fit actual')
        write_json(out/'actual_terminal.json',dict(status='completed',completed=True,exit_code=0,actual_fit_calls_attempted=attempted,
            actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,new_cash_accounts=0,new_labels=0,downloads=0,
            whole_database_hashes=0,fixture=False,elapsed_seconds=time.monotonic()-started))
        roles={'rff_mapping.npz':'shared_label_independent_random_map','predictions.csv.gz':'full_forward_predictions',
            'predictions_main.csv.gz':'main_cash_scores','predictions_holdout.csv.gz':'held_family_scores','held_diagnostic.json':'held_conditional_diagnostic',
            'held_daily.csv.gz':'held_u_equal_diagnostic','held_score_linkage.csv.gz':'full_held_state_linkage',
            'actual_started.json':'actual_start_audit','actual_terminal.json':'actual_terminal','input_bindings.json':'bound_input_references',
            'fit_attempts.jsonl':'actual_fit_attempt_journal','fit_completed.jsonl':'actual_fit_completion_journal',
            'fit_records.json':'all_model_bindings','opportunity_metrics.json':'opportunity_state_metrics','summary.json':'run_summary'}
        artifacts=[]
        for path in sorted(out.rglob('*')):
            if not path.is_file():continue
            relative=str(path.relative_to(out))
            role=roles.get(relative,{'scaler.json':'fold_train_only_scaler','training_identity_weights.csv.gz':'fold_training_identity_weights',
                'prediction_identity.csv.gz':'fold_prediction_identity','model.joblib':'ridge_model','portable_model.json':'portable_ridge',
                'normal_equations.npz':'ridge_normal_equations'}.get(path.name,'audit_artifact'))
            artifacts.append(dict(file_binding(path),role=role,reproducibility_required=True,raw_ohlc=False))
        manifest=dict(schema='stage094_crossday_order_fit_v1',status='completed',mode='actual',completed=True,protocol=file_binding(PROTOCOL),
            protocol_sha256=PROTOCOL_SHA,authorization=authorization_binding,terminal=file_binding(out/'actual_terminal.json'),source_bundle=bundle,
            input_bindings=auth['input_bindings'],rff_mapping=mapping_binding,predictions=all_binding,predictions_main=main_binding,predictions_holdout=held_binding,
            held_diagnostic=file_binding(out/'held_diagnostic.json'),held_daily=hd_binding,held_linkage=hl_binding,artifacts=artifacts,
            actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,prediction_rows=len(predictions),goal_complete=False,production_qualified=False)
        write_json(out/'manifest.json',manifest);return manifest
    except BaseException as error:
        if not (out/'actual_terminal.json').exists():write_json(out/'actual_terminal.json',dict(status='failed',completed=False,exit_code=1,
            actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,
            error_type=type(error).__name__,error=str(error),automatic_retry=False,elapsed_seconds=time.monotonic()-started))
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','protocol-sha256','authorization','authorization-sha256'):p.add_argument('--'+name,required=True)
    out,protocol,auth,binding=authorize(p.parse_args(argv))
    if legacy.sklearn.__version__!='1.6.1':raise ValueError('accepted sklearn1.6.1 runtime required')
    m=run_actual(out,protocol,auth,binding)
    print(json.dumps(dict(status=m['status'],output=str(out),actual_fit_calls_completed=m['actual_fit_calls_completed'])),flush=True)


if __name__=='__main__':main()
