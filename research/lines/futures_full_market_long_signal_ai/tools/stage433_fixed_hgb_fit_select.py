"""Frozen432: one fixed shallow HGB replaces Ridge on original130 design52.

Import and fixture do not read real arrays. Root authorizes exactly six actual
fits. Old rows/Y/weights/scalers, complete forward identities and156 K selection
are unchanged. No old-control fit, SQL, new labels, API or cash account.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import importlib.util
import io
import itertools
import json
from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage432_fixed_learner_protocol/protocol.json'
PROTOCOL_SHA='45c93399f2d6552a77805c9ca5bce9568b8e32522a5b6cdf5c289de11dbe847d'
CANDIDATE='COMMON52_FIXED_SHALLOW_HGB';END='2026-10-16'
SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01')
PARAMETERS=dict(loss='squared_error',learning_rate=.05,max_iter=100,max_leaf_nodes=7,max_depth=3,
    min_samples_leaf=100,l2_regularization=1.,max_bins=127,max_features=1.,categorical_features=None,
    early_stopping=False,warm_start=False,random_state=20261018)
SOURCE_NAMES=('stage433_fixed_hgb_fit_select.py','stage296_reopening_offset_fit_select.py',
    'stage285_wasde_offset_fit_select.py','stage130_contract_choice_fit.py',
    'stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py')
_HELPERS=None;_CACHED=None


def cached():
    global _CACHED
    if _CACHED is None:
        spec=importlib.util.spec_from_file_location('stage433_cached296',TOOLS/'stage296_reopening_offset_fit_select.py')
        _CACHED=importlib.util.module_from_spec(spec);spec.loader.exec_module(_CACHED)
    return _CACHED


def helpers():
    global _HELPERS
    if _HELPERS is None:_HELPERS=cached().helpers()
    return _HELPERS


def make_estimator():
    if sklearn.__version__!='1.6.1':raise ValueError('historical_fixed_HGB_requires_sklearn_1_6_1')
    return HistGradientBoostingRegressor(**PARAMETERS)


def export_model(model,feature_names):
    """Same numeric-node export as053, with actual52 feature identity explicit."""
    if len(feature_names)!=52 or model.n_features_in_!=52:raise ValueError('actual_common52_feature_identity')
    trees=[]
    for predictors in model._predictors:
        if len(predictors)!=1:raise ValueError('squared_error_single_tree_iteration')
        nodes=predictors[0].nodes
        if nodes['is_categorical'].any():raise ValueError('categorical_tree_outside_protocol')
        keys=('value','feature_idx','num_threshold','missing_go_to_left','left','right','is_leaf')
        trees.append([{k:float(r[k]) if k in ('value','num_threshold') else int(r[k]) for k in keys} for r in nodes])
    return dict(schema='stage433_portable_common52_numeric_hgb_v1',sklearn_version=sklearn.__version__,
        n_features=52,feature_names=list(feature_names),baseline=float(model._baseline_prediction.item()),
        leaf_values_include_learning_rate=True,formula='baseline + sum(reached_leaf.value); no extra learning_rate',
        parameters=PARAMETERS,trees=trees)


def portable_predict(model,x):
    x=np.asarray(x,float)
    if x.ndim!=2 or x.shape[1]!=52 or model['n_features']!=52 or not np.isfinite(x).all():raise ValueError('portable52_finite_design')
    scores=np.full(len(x),model['baseline'],float)
    for tree in model['trees']:
        for i,row in enumerate(x):
            n=0
            while not tree[n]['is_leaf']:
                node=tree[n];v=row[node['feature_idx']]
                left=node['missing_go_to_left'] if np.isnan(v) else v<=node['num_threshold']
                n=node['left'] if left else node['right']
            scores[i]+=tree[n]['value']
    return scores


def select_scope(mothers,scores,scope,calendar,end=END):
    selector=helpers().old_helper(True)
    def aliases():
        for row in scores:
            if row['scope']!=scope:raise ValueError('mixed_forward_scope')
            yield dict(row,scope='main')
    result=selector.select_full_pool(mothers,aliases(),calendar,end,audit_sink=lambda row:None)
    for row in result['choices']:row.update(scope=scope,candidate=CANDIDATE)
    return result


def source_bundle():
    return sorted((helpers().binding(TOOLS/n) for n in SOURCE_NAMES),key=lambda b:b['path'])


def authorize(args):
    h=helpers();out=Path(args.output).resolve();pb=h.binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen432_changed')
    if out.exists() or LINE/'outputs/stage433_fixed_hgb_fit_select' not in out.parents:raise ValueError('fresh_stage433_output_required')
    ab=h.binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('authorization_changed')
    auth=h.read_json(ab)
    required=dict(schema='stage433_exact_root_authorization_v1',authorized_by='root',exact_source_authorized=True,
        protocol_sha256=PROTOCOL_SHA,candidate=CANDIDATE,output=str(out),max_new_fit=6,max_new_cash=0)
    if any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle():raise ValueError('exact433_root_authorization_required')
    return out,h.read_json(pb),pb,auth,ab


def validate_inputs(p):
    h=helpers();inputs=p['inputs'];fit=h.read_json(inputs['fit_manifest'])
    if p['parameters']!=PARAMETERS or not h.same(inputs['fit_manifest'],p['identity_inputs']['original130_manifest']):raise ValueError('fixed432_parameters_or_original130')
    if fit.get('status')!='completed' or fit.get('actual_fit_calls_completed')!=6:raise ValueError('original130_completed_required')
    for role in ('mothers','actions'):
        if not h.same(inputs[role],fit['input_bindings'][role]):raise ValueError('original129_'+role)
    if not h.same(p['identity_inputs']['original_common'],fit['input_bindings']['common']) or not h.same(p['identity_inputs']['old_scores'],fit['child_scores']):raise ValueError('original_common_scores_identity')
    cm=h.read_json(inputs['control_choice_manifest']);held=h.read_json(inputs['control_held_manifest']);review=h.read_json(inputs['control_held_review'])
    if not h.same(cm['artifacts']['choices_main'],inputs['control_choices_main']) or cm['parent_rows']!=161014:raise ValueError('accepted156_main_control')
    if (not h.same(held['control_held_K'],inputs['control_held_choices']) or held.get('control_arm')!='COMMON52'
            or review.get('status')!='completed' or review.get('core_blockers')!=0
            or not h.same(review['manifest'],inputs['control_held_manifest'])):raise ValueError('accepted205_207_held_control')
    original=h.read_json(fit['fit_records'])
    if len(original)!=6:raise ValueError('six_original_fold_records')
    for f in p['identity_inputs']['original130_folds']:
        r=next(v for v in original if (v['scope'],v['cutoff'])==(f['scope'],f['cutoff']))
        for k in ('training_rows','training_dates','training_families','training_groups','prediction_children','prediction_mothers','max_u_date','max_label_known_date'):
            if r[k]!=f[k]:raise ValueError('original_fold_summary_'+k)
        for k in ('training_identity_weights','portable_model','scaler'):
            if not h.same(r[k],f[k]):raise ValueError('original_fold_binding_'+k)
    return inputs


def predicted_rows(path,common,models,scalers,writer,counters,statistics):
    selector=helpers().old_helper(True);old=helpers().old_helper()
    counters['score_csv_reads']+=1
    for chunk in pd.read_csv(path,usecols=selector.SCORE_FIELDS,dtype=str,keep_default_na=False,
            chunksize=100000,float_precision='round_trip'):
        counters['score_rows_read']+=len(chunk);chunk['old_score']=chunk.score.astype(float)
        if not np.isfinite(chunk.old_score).all():raise ValueError('old_forward_score_nonfinite')
        scores=np.empty(len(chunk),float)
        for key,idx in chunk.groupby(['scope','cutoff'],sort=False).indices.items():
            if key not in models:raise ValueError('forward_outside_six_fixed_folds')
            positions=np.asarray(idx,int);seq=chunk.iloc[positions].sequence_index.astype(np.int64).to_numpy()
            if (seq<0).any() or (seq>=len(common)).any():raise ValueError('forward_sequence_outside_common')
            x=old.design(common[seq],scalers[key])
            with threadpool_limits(limits=1):values=models[key].predict(x)
            if not np.isfinite(values).all():raise ValueError('HGB_forward_nonfinite')
            scores[positions]=values;counters['prediction_batches']+=1
            c=statistics.setdefault(key,Counter());c['rows']+=len(idx)
            c['negative_to_positive']+=int(np.count_nonzero((chunk.old_score.to_numpy()[positions]<=0)&(values>0)))
            c['positive_to_nonpositive']+=int(np.count_nonzero((chunk.old_score.to_numpy()[positions]>0)&(values<=0)))
        chunk['score']=scores
        for row in chunk.to_dict('records'):
            writer.writerow(row);yield row


def execute(args):
    out,p,pb,auth,ab=authorize(args);h=helpers();out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();bundle=source_bundle();artifacts={};folds=[];status='failed';error=None;changed_main=None;diagnostic=None
    counts=Counter(dict(fit_attempted=0,fit_completed=0,cash=0,SQL=0,old52_refit=0,new_labels=0,old_large_hash=0,
        common_reads=0,training_csv_reads=0,score_csv_reads=0,score_rows_read=0,mother_csv_reads=0,
        control_choice_reads=0,label_action_streams=0,prediction_batches=0,portable_anchor_predictions=0))
    def save_json(name,value):
        h.write_json(out/name,value);b=h.binding(out/name);artifacts[name.removesuffix('.json')]=b;return b
    def save_csv(name,value):
        value.to_csv(out/name,index=False,compression={'method':'gzip','mtime':0},float_format='%.17g')
        b=h.binding(out/name);artifacts[name.removesuffix('.csv.gz')]=b;return b
    save_json('started.json',dict(protocol=pb,authorization=ab,source_bundle=bundle,candidate=CANDIDATE,
        versions=dict(sklearn=sklearn.__version__,numpy=np.__version__,pandas=pd.__version__,joblib=joblib.__version__),automatic_retry=False))
    try:
        inputs=validate_inputs(p);selector=h.old_helper(True);old=h.old_helper()
        large={k:inputs[k] for k in ('mothers','actions','control_choices_main','control_held_choices')}
        large.update(common=p['identity_inputs']['original_common'],scores=p['identity_inputs']['old_scores'])
        for f in p['identity_inputs']['original130_folds']:large[f['scope']+'/'+f['cutoff']]=f['training_identity_weights']
        before={k:h.inherited_stat(b) for k,b in large.items()}
        cal=np.load(io.BytesIO(h.read_small(inputs['calendar'])),allow_pickle=False)
        calendar=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in cal]
            if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('original_calendar')
        mothers=pd.read_csv(inputs['mothers']['path'],usecols=selector.IDENTITY,dtype=str,keep_default_na=False);counts['mother_csv_reads']+=1
        for k in ('sequence_index','u_index'):mothers[k]=mothers[k].astype(np.int64)
        if (len(mothers)!=399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique()!=98
                or mothers.family_id.nunique()!=95 or not np.array_equal(mothers.sequence_index,np.arange(399252))
                or not np.array_equal(mothers.u_date,np.asarray(calendar)[mothers.u_index.to_numpy()])):raise ValueError('original_full_mothers')
        forward=mothers.loc[mothers.u_date.ge(CUTOFFS[0])&mothers.u_date.le(END)].reset_index(drop=True)
        if len(forward)!=161014:raise ValueError('full_forward_parents')
        with np.load(p['identity_inputs']['original_common']['path'],allow_pickle=False) as z:common=z['common'];columns=z['columns'].tolist()
        counts['common_reads']+=1
        if common.shape!=(1552456,26) or columns!=old.COMMON:raise ValueError('original_common26_identity')
        models={};scalers={}
        for f in p['identity_inputs']['original130_folds']:
            scope,cutoff=f['scope'],f['cutoff'];key=(scope,cutoff);scaler=h.read_json(f['scaler'])
            if (scaler['feature_names']!=old.FEATURE_NAMES or scaler['common']['columns']!=columns
                    or scaler['scope']!=scope or scaler['cutoff']!=cutoff):raise ValueError('own_fold_original_scaler')
            frame=pd.read_csv(f['training_identity_weights']['path'],usecols=h.TRAIN_FIELDS,dtype=str,keep_default_na=False)
            counts['training_csv_reads']+=1;train=cached().validate_training(frame,scope,cutoff,f['training_rows'])
            if (train.u_date.nunique()!=f['training_dates'] or train.family_id.nunique()!=f['training_families']
                    or train.u_date.max()!=f['max_u_date'] or train.label_known_date.max()!=f['max_label_known_date']
                    or train.sequence_index.max()>=len(common)
                    or not np.array_equal(train.u_date,np.asarray(calendar)[train.u_index.to_numpy()])):raise ValueError('original_training_summary_calendar')
            seq=train.sequence_index.to_numpy();x=old.design(common[seq],scaler)
            y=train.net_R_stress.to_numpy();w=train.sample_weight.to_numpy();model=make_estimator()
            counts['fit_attempted']+=1;save_json('fit_attempt_'+str(counts['fit_attempted'])+'.json',dict(scope=scope,cutoff=cutoff,**dict(counts)))
            with threadpool_limits(limits=1):model.fit(x,y,sample_weight=w)
            counts['fit_completed']+=1;models[key]=model;scalers[key]=scaler
            portable=export_model(model,old.FEATURE_NAMES)
            anchors=np.unique(np.linspace(0,len(x)-1,min(64,len(x)),dtype=int));xp=x[anchors]
            with threadpool_limits(limits=1):direct=model.predict(xp)
            external=portable_predict(portable,xp);maxerr=float(np.max(np.abs(direct-external)))
            counts['portable_anchor_predictions']+=len(anchors)
            if not np.allclose(direct,external,rtol=1e-12,atol=1e-12):raise ValueError('portable_HGB_anchor_mismatch')
            stem=scope+'_'+cutoff;portable.update(scope=scope,cutoff=cutoff,candidate=CANDIDATE,
                scaler=f['scaler'],training_identity_weights=f['training_identity_weights'])
            mb=save_json('portable_'+stem+'.json',portable)
            modelpath=out/('model_'+stem+'.joblib')
            with modelpath.open('xb') as stream:joblib.dump(model,stream,compress=3)
            jb=h.binding(modelpath);artifacts['model_'+stem]=jb
            record=dict(scope=scope,cutoff=cutoff,training_rows=len(train),training_dates=int(train.u_date.nunique()),
                training_families=int(train.family_id.nunique()),training_groups=f['training_groups'],
                max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
                sample_weight_sum=float(w.sum()),target='unchanged original129 net_R_stress',dimension=52,
                training_identity_weights=f['training_identity_weights'],scaler=f['scaler'],original_control_model=f['portable_model'],
                model=jb,portable_model=mb,parameters=PARAMETERS,n_iter=int(model.n_iter_),
                prediction_children=f['prediction_children'],prediction_mothers=f['prediction_mothers'],
                portable_anchor_count=len(anchors),portable_max_abs_error=maxerr,training_weights_renormalized=False)
            folds.append(record);save_json('fold_'+stem+'.json',record)
            del x,xp,frame,train
            print(json.dumps(dict(phase='HGB_fold_complete',scope=scope,cutoff=cutoff,completed=counts['fit_completed'])),flush=True)
        if counts['fit_attempted']!=6 or counts['fit_completed']!=6:raise ValueError('exact_six_HGB_fits')
        summaries=[];choices=[];boundaries={};stats={};seen=[]
        scorepath=out/'child_scores.csv.gz'
        with gzip.open(scorepath,'xt',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=selector.SCORE_FIELDS+['old_score']);writer.writeheader()
            rows=predicted_rows(p['identity_inputs']['old_scores']['path'],common,models,scalers,writer,counts,stats)
            for scope,part in itertools.groupby(rows,key=lambda r:r['scope']):
                if scope not in SCOPES or scope in seen:raise ValueError('noncontiguous_or_unknown_score_scope')
                seen.append(scope)
                parents=forward if scope=='main' else forward.loc[forward.family_id.map(old.family_group).eq(int(scope[-1]))]
                result=select_scope(parents.to_dict('records'),part,scope,calendar)
                choices.append(pd.DataFrame(result['choices']));summaries.append(dict(scope=scope,**result['summary']))
                for epoch,b in result['boundaries'].items():
                    if epoch in boundaries and boundaries[epoch]!=b:raise ValueError('K_boundary_changed')
                    boundaries[epoch]=b
                print(json.dumps(dict(phase='full_scope_selection_complete',scope=scope,parent_rows=len(result['choices']))),flush=True)
        artifacts['child_scores']=h.binding(scorepath)
        if seen!=list(SCOPES) or counts['score_rows_read']!=1933480:raise ValueError('full_original_forward_score_domain')
        for f in p['identity_inputs']['original130_folds']:
            if stats.get((f['scope'],f['cutoff']),{}).get('rows')!=f['prediction_children']:raise ValueError('complete_fold_children')
        combined=pd.concat(choices,ignore_index=True);main=combined.loc[combined.scope.eq('main')].sort_values('sequence_index').reset_index(drop=True)
        held=combined.loc[combined.scope.ne('main')].sort_values('sequence_index').reset_index(drop=True)
        for frame in (main,held):
            if len(frame)!=161014 or frame.event_id.tolist()!=forward.event_id.tolist():raise ValueError('complete_main_held_parent_union')
        control=cached().read_choices(inputs['control_choices_main'],forward)
        oldheld=cached().read_choices(inputs['control_held_choices'],forward,True);counts['control_choice_reads']+=2
        changed_main=int(np.count_nonzero(main.chosen_action_id.to_numpy()!=control.chosen_action_id.to_numpy()))
        changed_held=int(np.count_nonzero(held.chosen_action_id.to_numpy()!=oldheld.chosen_action_id.to_numpy()))
        if changed_held:
            ids=set(oldheld.loc[oldheld.selected.eq(1),'chosen_action_id'])|set(held.loc[held.selected.eq(1),'chosen_action_id'])
            labels=cached().label_subset(inputs['actions']['path'],ids,counts)
        else:
            labels=pd.DataFrame(columns=cached().LABEL_FIELDS);labels['net_R_stress']=pd.Series(dtype=float)
        diagnostic,daily=cached().held_diagnostic(oldheld,held,labels,labels_skipped=not changed_held)
        diagnostic.update(schema='stage433_fixed_hgb_held_original_target_v1',candidate=CANDIDATE,
            not_cash_admission_veto=True,target='original129 net_R_stress first-exit; not K funded cash')
        save_csv('choices_main.csv.gz',main);save_csv('choices_holdout.csv.gz',held)
        save_json('boundaries.json',dict(schema='stage156_voluntary_K_only_v1',epochs=boundaries,
            policy_version=selector.POLICY_VERSION,sample_end=END,calendar=inputs['calendar'],account_deadline_certified=False))
        save_json('held_diagnostic.json',diagnostic);save_csv('held_daily.csv.gz',daily)
        save_json('selection_summary.json',dict(scopes=summaries,changed_main_parent_choices=changed_main,
            changed_held_parent_choices=changed_held,same_K_controls=True,cash_eligible=bool(changed_main),held_diagnostic_is_cash_veto=False))
        save_json('forward_summary.json',dict(folds=[dict(scope=k[0],cutoff=k[1],**dict(v)) for k,v in stats.items()],
            full_score_identities_preserved=True,source_score_rows=1933480))
        save_json('fit_records.json',folds)
        after={k:h.inherited_stat(b) for k,b in large.items()}
        if after!=before or source_bundle()!=bundle:raise ValueError('source_or_inherited_input_stat_changed')
        save_json('input_stat_receipt.json',dict(before=before,after=after,old_large_hashes=0))
        status='completed'
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        save_json('terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,error=error,
            elapsed_seconds=time.monotonic()-started,counters=dict(counts),automatic_retry=False,new_cash=0))
    manifest=dict(schema='stage433_fixed_hgb_fit_select_manifest_v1',status=status,protocol=pb,protocol_sha256=PROTOCOL_SHA,
        candidate=CANDIDATE,source_bundle=bundle,authorization=ab,inputs=inputs,artifacts=artifacts,folds=folds,counters=dict(counts),
        changed_main_parent_choices=changed_main,cash_eligible=bool(changed_main),held_diagnostic_is_cash_veto=False,
        new_cash=0,old_control_refit=0,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
    h.write_json(out/'manifest.json',manifest)
    return dict(status=status,output=str(out),fit_completed=counts['fit_completed'],new_cash=0,changed_main_parent_choices=changed_main)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args(argv)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
