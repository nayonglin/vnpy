"""Frozen217 DOMAIN52 loss-domain intervention; root-only actual execution.

Original130 labels,52 design,scalers and relative weights are reused. Only the
fixed156 actionable training support changes; six preflights precede every fit.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage217_training_domain_loss_protocol/protocol.json'
PROTOCOL_SHA='b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53'
OUTPUT=LINE/'outputs/stage218_training_domain_loss_fit/actual_run1'
SCOPES=('main','holdout_0','holdout_1');CUTOFFS=('2020-01-01','2023-01-01');END='2026-10-16'
CANDIDATE='DOMAIN52';CONTROL='COMMON52';PARAMETERS=dict(alpha=1.,fit_intercept=True,solver='cholesky')
_HELPERS=None


def helpers():
    global _HELPERS
    if _HELPERS is None:
        modules=[]
        for name in ('stage205_local_curve_information_fit','stage214_training_domain_probe'):
            spec=importlib.util.spec_from_file_location('stage218_'+name,TOOLS/(name+'.py'))
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules.append(module)
        _HELPERS=tuple(modules)
    return _HELPERS


def source_bundle():
    shared,_=helpers()
    return sorted([shared.file_binding(TOOLS/n) for n in (
        'stage218_training_domain_loss_fit.py','test_stage218_training_domain_loss_fit.py',
        'stage205_local_curve_information_fit.py','stage214_training_domain_probe.py',
        'stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py',
        'stage156_voluntary_choices.py')],key=lambda b:b['path'])


def write_json(path,value):
    return helpers()[0].write_json(path,value)


def inherited_stat(bound):
    return helpers()[0].inherited_stat(bound)


def load_inputs(inputs,counters):
    shared,_=helpers();old,_=shared.helpers()
    roles=('dataset_manifest','dataset_terminal','control_fit_manifest','control_fit_records',
        'market_protocol','training_domain_manifest','training_domain_summary','training_domain_review',
        'domain_decision','control_choice_manifest','control_held_K_manifest','control_held_K_review')
    small={r:json.loads(shared.read_bound(inputs[r])) for r in roles}
    if small['dataset_manifest'].get('status')!='completed' or small['dataset_terminal'].get('status')!='completed':
        raise ValueError('original129_incomplete')
    for role in ('actions','common','mothers'):
        if not shared.same_binding(small['dataset_manifest'].get(role,{}),inputs[role]):
            raise ValueError('original129_binding_'+role)
    fit=small['control_fit_manifest'];records=small['control_fit_records']
    if (fit.get('status')!='completed' or fit.get('actual_fit_calls_attempted')!=6
            or fit.get('actual_fit_calls_completed')!=6
            or not shared.same_binding(fit.get('fit_records',{}),inputs['control_fit_records'])):
        raise ValueError('accepted130_fit_identity_differs')
    for role in ('actions','common','mothers','dataset_manifest','dataset_terminal'):
        if not shared.same_binding(fit['input_bindings'].get(role,{}),inputs[role]):
            raise ValueError('accepted130_original_binding_'+role)
    domain=small['training_domain_manifest'];review=small['training_domain_review']
    if (domain.get('status')!='completed' or review.get('status')!='completed' or review.get('core_blockers')!=0
            or not shared.same_binding(review.get('implementation_manifest',{}),inputs['training_domain_manifest'])
            or not shared.same_binding(domain.get('summary',{}),inputs['training_domain_summary'])
            or small['domain_decision'].get('status')!='domain_difference_accepted_separate_single_loss_experiment_worth_freezing'):
        raise ValueError('accepted214_215_216_lineage_differs')
    domain_folds={(f['scope'],f['cutoff']):f for f in domain['folds']}
    for record in records:
        previous=domain_folds.get((record['scope'],record['cutoff']),{})
        if (previous.get('training_rows')!=record['training_rows']
                or not shared.same_binding(previous.get('training_cache',{}),record['training_identity_weights'])):
            raise ValueError('accepted214_original_training_cache_differs')
    if (not shared.same_binding(small['market_protocol']['calendar'],inputs['calendar'])
            or not shared.same_binding(small['control_choice_manifest']['artifacts']['choices_main'],inputs['control_choices_main_K'])
            or not shared.same_binding(small['control_held_K_manifest'].get('control_held_K',{}),inputs['control_held_K'])
            or small['control_held_K_review'].get('core_blockers')!=0
            or not shared.same_binding(small['control_held_K_review'].get('manifest',{}),inputs['control_held_K_manifest'])):
        raise ValueError('accepted_calendar_or_control_choices_differs')
    inherited={r:inputs[r] for r in ('actions','mothers','common','control_choices_main_K','control_held_K')}
    for record in records:inherited['training_weights/'+record['scope']+'/'+record['cutoff']]=record['training_identity_weights']
    before={r:shared.inherited_stat(b) for r,b in inherited.items()}
    counters['action_csv_reads']+=1
    a=pd.read_csv(inputs['actions']['path'],usecols=shared.ACTION_FIELDS,dtype=str,keep_default_na=False,float_precision='round_trip')
    for field in shared.NUMERIC:a[field]=pd.to_numeric(a[field],errors='coerce')
    counters['mother_csv_reads']+=1
    m=pd.read_csv(inputs['mothers']['path'],usecols=old.IDENTITY,dtype=str,keep_default_na=False)
    for field in ('sequence_index','u_index'):m[field]=pd.to_numeric(m[field],errors='raise')
    if len(m)!=399252 or m.event_id.duplicated().any() or not np.array_equal(m.sequence_index,np.arange(len(m))):
        raise ValueError('full_original_mother_identity_differs')
    if (len(a)!=1552456 or a.action_id.duplicated().any() or not np.array_equal(a.sequence_index,np.arange(len(a)))
            or not a.sequence_index.eq(a.action_sequence_index).all() or not a.event_id.eq(a.action_id).all()
            or not a.reference_epoch.eq(a.actual_epoch).all()):raise ValueError('full_original_action_identity_differs')
    pi=a.mother_sequence_index.to_numpy(np.int64)
    if (pi<0).any() or (pi>=len(m)).any():raise ValueError('invalid_parent_sequence')
    for left,right in [('mother_event_id','event_id'),('product_id','product_id'),('family_id','family_id'),
        ('u_date','u_date'),('u_index','u_index'),('anchor_epoch','reference_epoch')]:
        if not np.array_equal(a[left].to_numpy(),m[right].to_numpy()[pi]):raise ValueError('original_parent_child_'+left)
    if not a.u_action_eligible.isin([0,1]).all():raise ValueError('original_eligibility_differs')
    counters['common_npz_reads']+=1
    with np.load(inputs['common']['path'],allow_pickle=False) as data:
        if data['columns'].tolist()!=old.COMMON or data['common'].shape!=(len(a),26):raise ValueError('original_common_shape_differs')
        common=data['common'].astype(float)
    counters['calendar_reads']+=1
    arr=np.load(io.BytesIO(shared.read_bound(inputs['calendar'])),allow_pickle=False)
    calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in arr]
              if arr.dtype.kind in 'iu' else arr.astype('datetime64[D]').astype(str).tolist())
    if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('full_calendar_differs')
    return a,m,common,calendar,records,small['training_domain_summary'],inherited,before


def domain_weights(u_indexes,epochs,weights,calendar):
    shared,probe=helpers();_,voluntary=shared.helpers()
    w=np.asarray(weights,float)
    if (w.ndim!=1 or len(w)!=len(u_indexes) or len(w)!=len(epochs)
            or not np.isfinite(w).all() or (w<=0).any()):raise ValueError('invalid_original_weights')
    boundaries={e:voluntary.calendar_boundary(e,calendar,END) for e in sorted(set(epochs))}
    states=[probe.action_gate(int(u),e,calendar,boundaries[e])['partition'] for u,e in zip(u_indexes,epochs)]
    mask=np.asarray([s=='admissible' for s in states],bool);unknown=sum(s=='unknown' for s in states)
    W=math.fsum(w);WA=math.fsum(w[mask]);factor=W/WA if WA>0 else None
    candidate=w[mask]*factor if factor is not None else np.empty(0,float)
    ready=bool(len(w)>0 and mask.any() and not unknown and np.isfinite(candidate).all() and (candidate>0).all())
    ess=lambda x:math.fsum(x)**2/math.fsum(float(v)*float(v) for v in x) if len(x) else None
    report=dict(ready=ready,original_rows=len(w),retained_rows=int(mask.sum()),excluded_rows=int((~mask).sum()),
        gate_unknown_rows=unknown,old_weight_mass=W,admissible_old_weight_mass=WA,
        excluded_old_weight_mass=math.fsum(w[~mask]),weight_uniform_factor=factor,
        candidate_weight_mass=math.fsum(candidate),candidate_mass_residual=math.fsum(candidate)-W if factor is not None else None,
        old_effective_sample_size=ess(w),retained_old_effective_sample_size=ess(w[mask]),
        candidate_effective_sample_size=ess(candidate),uniqueness_recomputed=False,
        relative_retained_weights_preserved=True,total_loss_mass_preserved=ready and abs(math.fsum(candidate)-W)<=8*math.ulp(W))
    if ready and not report['total_loss_mass_preserved']:raise ValueError('candidate_total_loss_mass_differs')
    return mask,candidate,report


def prepare_folds(actions,mothers,common,calendar,records,domain_summary,counters):
    shared,_=helpers();old,_=shared.helpers();plans=[];reports=[]
    by_fold={(r['scope'],r['cutoff']):r for r in records}
    accepted={(r['scope'],r['cutoff']):r for r in domain_summary['folds']}
    expected={(s,c) for s in SCOPES for c in CUTOFFS}
    if len(records)!=6 or set(by_fold)!=expected or len(accepted)!=6 or set(accepted)!=expected:
        raise ValueError('exact_six_original_and_domain_folds_required')
    for scope in SCOPES:
        for j,cutoff in enumerate(CUTOFFS):
            record=by_fold[(scope,cutoff)];reference=accepted[(scope,cutoff)]
            train,pred,parent=old.fold_slices(actions,mothers,cutoff,CUTOFFS[j+1] if j+1<len(CUTOFFS) else None,scope)
            counters['training_weight_csv_reads']+=1
            cached=pd.read_csv(record['training_identity_weights']['path'],usecols=shared.TRAIN_MATCH_FIELDS+['sample_weight'],
                dtype=str,keep_default_na=False,float_precision='round_trip');shared.parse_cached_numeric(cached)
            if len(cached)!=len(train) or len(train)!=record['training_rows']:raise ValueError('original_training_row_count_differs')
            for field in shared.TRAIN_MATCH_FIELDS:
                left,right=cached[field].to_numpy(),train[field].to_numpy()
                same=np.array_equal(left,right,equal_nan=True) if field in shared.NUMERIC else np.array_equal(left,right)
                if not same:raise ValueError('original_training_identity_differs '+scope+' '+cutoff+' '+field)
            w=cached.sample_weight.to_numpy(float);ti=train.sequence_index.to_numpy(np.int64)
            if not np.isfinite(train.net_R_stress).all():raise ValueError('original_train_target_nonfinite')
            mask,candidate_weight,domain=domain_weights(train.u_index.to_numpy(np.int64),train.reference_epoch.to_numpy(),w,calendar)
            if (domain['original_rows']!=reference['rows'] or domain['retained_rows']!=reference['admissible_rows']
                    or domain['excluded_rows']!=reference['inadmissible_rows']+reference['unknown_rows']
                    or domain['gate_unknown_rows']!=reference['unknown_rows']):raise ValueError('accepted214_domain_counts_differs')
            for left,right in [('old_weight_mass','old_weight_mass'),('admissible_old_weight_mass','admissible_old_weight_mass')]:
                if domain[left]!=reference[right]:raise ValueError('accepted214_original_mass_differs '+left)
            scaler=json.loads(shared.read_bound(record['scaler']))
            if (scaler.get('scope')!=scope or scaler.get('cutoff')!=cutoff or scaler.get('feature_names')!=old.FEATURE_NAMES
                    or scaler.get('common',{}).get('columns')!=old.COMMON):raise ValueError('original_common_scaler_differs')
            for start in range(0,len(ti),65536):old.design(common[ti[start:start+65536]],scaler)
            report=dict(scope=scope,cutoff=cutoff,training_rows=len(ti),training_dates=int(train.u_date.nunique()),
                training_families=int(train.family_id.nunique()),training_groups=record['training_groups'],
                prediction_children=len(pred),prediction_mothers=len(parent),max_u_date=str(train.u_date.max()),
                max_label_known_date=str(train.label_known_date.max()),domain=domain,full52_design_finite=True,
                training_identity_weights=record['training_identity_weights'],common_scaler=record['scaler'],
                training_identity_match_fields=shared.TRAIN_MATCH_FIELDS,training_weights_recomputed=False)
            if any(report[k]!=record[k] for k in ('training_dates','training_families','prediction_children','prediction_mothers','max_u_date','max_label_known_date')):
                raise ValueError('accepted130_fold_support_differs')
            plans.append(dict(report=report,original_ti=ti,mask=mask,ti=ti[mask],old_weights=w,weights=candidate_weight,
                pi=pred.sequence_index.to_numpy(np.int64),mi=parent.sequence_index.to_numpy(np.int64),common_scaler=scaler))
            reports.append(report)
    return plans,dict(schema='stage218_all_six_loss_support_preflight_v1',ready=all(r['domain']['ready'] for r in reports),
        cells=reports,exact_six_unique_folds=True,all_support_before_any_fit=True,new_labels=0,new_scalers=0)


def gated_fits(preflight,callback):
    cells=preflight.get('cells',[])
    complete=len(cells)==6 and {(r['scope'],r['cutoff']) for r in cells}=={(s,c) for s in SCOPES for c in CUTOFFS}
    return callback() if preflight.get('ready') and complete and all(r['domain']['ready'] for r in cells) else None


def fit_arrays(x,y,weights,on_complete):
    shared,_=helpers();old,_=shared.helpers()
    if x.shape!=(len(y),52) or len(weights)!=len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('fixed52_fit_shape_or_finite_differs')
    estimator=old.legacy.Ridge(**PARAMETERS)
    with old.legacy.threadpool_limits(limits=1):estimator.fit(x,y,sample_weight=weights)
    on_complete()
    z=np.column_stack((x,np.ones(len(x))));lhs=z.T@(weights[:,None]*z)
    lhs[np.arange(52),np.arange(52)]+=PARAMETERS['alpha'];rhs=z.T@(weights*y)
    beta=np.r_[estimator.coef_,estimator.intercept_];residual=lhs@beta-rhs
    if not np.isfinite(beta).all() or not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):raise ValueError('ridge_normal_equations_mismatch')
    return dict(schema='stage218_portable_ridge52_v1',parameters=PARAMETERS,coef=estimator.coef_.tolist(),
        intercept=float(estimator.intercept_)),dict(lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,
        weight_sum=np.array(math.fsum(weights))),float(np.max(np.abs(residual)))


def selection_identity(candidate,control):
    identity=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch']
    action=['chosen_action_id','chosen_action_sequence_index','chosen_epoch','selected']
    aa=candidate.sort_values('sequence_index',kind='stable').reset_index(drop=True)
    bb=control.sort_values('sequence_index',kind='stable').reset_index(drop=True)
    if len(aa)!=len(bb) or aa.event_id.duplicated().any() or bb.event_id.duplicated().any():raise ValueError('main_control_parent_domain_differs')
    numeric={'sequence_index','u_index','chosen_action_sequence_index','selected'}
    differences={};changed=np.zeros(len(aa),bool)
    for field in identity+action:
        left=aa[field].astype(float).to_numpy() if field in numeric else aa[field].to_numpy()
        right=bb[field].astype(float).to_numpy() if field in numeric else bb[field].to_numpy()
        different=left!=right;differences[field]=int(different.sum())
        if field in identity and different.any():raise ValueError('main_control_identity_differs '+field)
        changed|=different
    return dict(schema='stage218_main_action_identity_v1',full_parent_rows=len(aa),
        compared_fields=identity+action,differences_by_field=differences,changed_parent_rows=int(changed.sum()),
        identical_actions=not bool(changed.any()),cash_eligible=bool(changed.any()),
        score_magnitude_used_for_sizing_or_priority=False,
        reason='changed_main_actions_require_four_new_own_cash_books' if changed.any() else 'no_action_change')


def forward_and_select(a,m,common,calendar,plans,models,inputs,counters,save_json,save_csv):
    shared,_=helpers();old,voluntary=shared.helpers();children=[]
    seen={True:np.zeros(len(a),bool),False:np.zeros(len(a),bool)}
    for plan,model in zip(plans,models):
        r=plan['report'];pi=plan['pi'];scope=r['scope'];cutoff=r['cutoff']
        counters['prediction_calls_attempted']+=1;xp=old.design(common[pi],plan['common_scaler'])
        scores=xp@np.asarray(model['coef'],float)+model['intercept']
        if not np.isfinite(scores).all():raise ValueError('nonfinite_forward_score')
        counters['prediction_calls_completed']+=1;counters['prediction_model_rows']+=len(pi)
        if seen[scope=='main'][pi].any():raise ValueError('duplicate_forward_child_identity')
        seen[scope=='main'][pi]=True
        child=a.iloc[pi][shared.CHILD_FIELDS].copy();child['score']=scores;child['scope']=scope;child['cutoff']=cutoff;child['arm']=CANDIDATE
        children.append(child);del xp
    expected=a.u_date.ge(CUTOFFS[0]).to_numpy()
    if counters['prediction_model_rows']!=1933480 or int(expected.sum())!=966740 or any(not np.array_equal(v,expected) for v in seen.values()):
        raise ValueError('full_forward_child_domain_differs')
    children=pd.concat(children,ignore_index=True);choices=[];boundaries={};summaries=[]
    for scope in SCOPES:
        part=children.loc[children.scope.eq(scope)];mothers=m.loc[m.u_date.ge(CUTOFFS[0])]
        if scope!='main':mothers=mothers.loc[mothers.family_id.map(old.family_group).eq(int(scope[-1]))]
        counters['candidate_selection_calls']+=1
        chosen,new_bounds,summary=shared.choose_scope(mothers,part,scope,CANDIDATE,calendar)
        choices.append(chosen);summaries.append(dict(arm=CANDIDATE,scope=scope,summary=summary))
        for epoch,value in new_bounds.items():
            if epoch in boundaries and boundaries[epoch]!=value:raise ValueError('shared_K_boundary_differs')
            boundaries[epoch]=value
    choices=pd.concat(choices,ignore_index=True)
    main=choices.loc[choices.scope.eq('main')].sort_values('sequence_index',kind='stable').reset_index(drop=True)
    held=choices.loc[choices.scope.ne('main')].sort_values('sequence_index',kind='stable').reset_index(drop=True)
    controls={}
    for role in ('control_choices_main_K','control_held_K'):
        counters['control_choices_csv_reads']+=1
        frame=pd.read_csv(inputs[role]['path'],dtype=str,keep_default_na=False,float_precision='round_trip')
        for field in ('sequence_index','u_index','chosen_action_sequence_index','selected'):frame[field]=frame[field].astype(np.int64)
        controls[role]=frame.sort_values('sequence_index',kind='stable').reset_index(drop=True)
    expected_parents=set(m.loc[m.u_date.ge(CUTOFFS[0]),'event_id'])
    for name,frame in [('candidate_main',main),('candidate_held',held),*controls.items()]:
        if len(frame)!=161014 or frame.event_id.duplicated().any() or set(frame.event_id)!=expected_parents:
            raise ValueError('complete_parent_identity_differs '+name)
    if set(boundaries)!=set(a.loc[expected,'reference_epoch']):raise ValueError('full_epoch_K_domain_differs')
    identity=selection_identity(main,controls['control_choices_main_K'])
    comparison=pd.concat([controls['control_held_K'].assign(arm='A'),held.assign(arm='B')],ignore_index=True)
    diagnostic,daily,_=old.held_diagnostics(comparison,a)
    diagnostic.update(schema='stage218_domain52_held_K_original_target_diagnostic_v1',arm_aliases={'A':CONTROL,'B':CANDIDATE},
        contrast=CANDIDATE+'_minus_'+CONTROL,target='unchanged original129 firstexit net_R_stress; not K-truncated outcome',
        strictPIT_certified=False)
    for group in diagnostic['groups'].values():
        mean=group['known_u_equal_mean_increment_R'];unknown=group['unknown_differential_selected_events']
        group['nominal_pass']=bool(mean is not None and mean>0 and unknown==0)
        group['selected_by_arm']={CONTROL:group['selected_by_arm']['A'],CANDIDATE:group['selected_by_arm']['B']}
    out={role:save_csv(role+'.csv.gz',frame) for role,frame in (
        ('child_scores',children),('choices_main',main),('choices_holdout',held),('held_daily',daily))}
    out['held_diagnostic']=save_json('held_diagnostic.json',diagnostic)
    out['selection_identity']=save_json('selection_identity.json',identity)
    out['boundaries']=save_json('boundaries.json',dict(schema='stage218_fixed155_K_boundaries_v1',epochs=boundaries,
        policy_version=voluntary.POLICY_VERSION,sample_end=END,calendar=inputs['calendar'],account_deadline_certified=False))
    out['selection_summary']=save_json('selection_summary.json',summaries)
    return out,identity


def authorize(args):
    shared,_=helpers();output=Path(args.output).resolve()
    if output!=OUTPUT or output.exists():raise ValueError('fresh_exact_stage218_actual_run1_required')
    protocol_binding=shared.file_binding(PROTOCOL)
    if protocol_binding['sha256']!=PROTOCOL_SHA:raise ValueError('frozen217_protocol_differs')
    protocol=json.loads(shared.read_bound(protocol_binding));auth_binding=shared.file_binding(args.authorization)
    if auth_binding['sha256']!=args.authorization_sha256:raise ValueError('root_binding_sha_differs')
    auth=json.loads(shared.read_bound(auth_binding))
    required=dict(schema='stage217_exact_root_fit_authorization_v1',authorized_by='root',stage='fit',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
    if (any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle()
            or auth.get('input_bindings')!=protocol['input_bindings']):raise ValueError('exact_root_source_authorization_differs')
    return output,auth,auth_binding,protocol_binding


def run_actual(output,auth,authorization,protocol_binding):
    shared,_=helpers();old,_=shared.helpers();output=Path(output);output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();bundle=source_bundle();artifacts={};roles={};records=[];evidence={}
    counters=dict(fit_calls_attempted=0,fit_calls_completed=0,old_fit=0,cash=0,old_cash=0,SQL=0,
        source_projection=0,new_labels=0,downloads=0,large_input_hash_scans=0,action_csv_reads=0,mother_csv_reads=0,
        common_npz_reads=0,q_npz_reads=0,calendar_reads=0,training_weight_csv_reads=0,training_weights_recomputed=0,
        control_score_csv_reads=0,control_choices_csv_reads=0,prediction_calls_attempted=0,prediction_calls_completed=0,
        prediction_model_rows=0,candidate_selection_calls=0,control_held_selection_calls=0,control_main_selection_calls=0)
    def save_json(name,obj):
        shared.write_json(output/name,obj);b=shared.file_binding(output/name);artifacts[name]=b;return b
    def save_csv(name,frame):
        frame.to_csv(output/name,index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
        b=shared.file_binding(output/name);artifacts[name]=b;return b
    def save_npz(name,**values):
        with (output/name).open('xb') as stream:np.savez_compressed(stream,**values)
        b=shared.file_binding(output/name);artifacts[name]=b;return b
    def checkpoint(name,scope,cutoff,count):
        with (output/name).open('a') as stream:
            stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,count=count))+'\n');stream.flush()
    save_json('started.json',dict(status='started',started_at=datetime.now(timezone.utc).isoformat(),
        protocol=protocol_binding,authorization=authorization,source_bundle=bundle,automatic_retry=False))
    def finish(cash_eligible,reason):
        if bundle!=source_bundle():raise ValueError('source_changed_during_actual')
        if evidence:
            evidence['after']={r:shared.inherited_stat(b) for r,b in evidence['bindings'].items()}
            if evidence['before']!=evidence['after']:raise ValueError('inherited_sources_changed_during_actual')
        for name in ('fit_attempts.jsonl','fit_completed.jsonl'):
            if (output/name).exists():artifacts[name]=shared.file_binding(output/name)
        summary=dict(status='completed',reason=reason,counters=counters,
            actual_fit_calls_attempted=counters['fit_calls_attempted'],actual_fit_calls_completed=counters['fit_calls_completed'],
            actual_model_fit_calls=counters['fit_calls_completed'],new_cash=0,new_SQL=0,
            cumulative_fit=427+counters['fit_calls_completed'],cumulative_cash=230,cash_eligible=cash_eligible,
            goal_complete=False,production_qualified=False,alpha_qualified=False)
        roles['summary']=save_json('summary.json',summary)
        terminal=save_json('terminal.json',dict(**summary,exit_code=0,elapsed_seconds=time.monotonic()-started,automatic_retry=False))
        manifest=dict(schema='stage218_training_domain_loss_fit_v1',**summary,protocol=protocol_binding,
            protocol_sha256=PROTOCOL_SHA,source_bundle=bundle,authorization=authorization,input_bindings=auth['input_bindings'],
            source_read_receipt=evidence,artifacts=artifacts.copy(),terminal=terminal,
            prediction_mothers_per_arm=161014 if counters['prediction_model_rows'] else 0,
            prediction_children=counters['prediction_model_rows'],candidate_arm=CANDIDATE,control_arm=CONTROL,
            control_choices_main_reused=auth['input_bindings']['control_choices_main_K'],control_held_K_reused=auth['input_bindings']['control_held_K'],
            interpretation='single empirical loss-support intervention; original target/scaler/relative weights unchanged',**roles)
        shared.write_json(output/'manifest.json',manifest);return manifest
    try:
        a,m,common,calendar,old_records,domain_summary,inherited,before=load_inputs(auth['input_bindings'],counters)
        evidence=dict(bindings=inherited,before=before)
        plans,preflight=prepare_folds(a,m,common,calendar,old_records,domain_summary,counters)
        roles['preflight']=save_json('preflight.json',preflight)
        def do_all_fits():
            models=[];y_all=a.net_R_stress.to_numpy(float)
            for plan in plans:
                report=plan['report'];scope=report['scope'];cutoff=report['cutoff'];ti=plan['ti']
                folder=Path('folds')/scope/cutoff;(output/folder).mkdir(parents=True,exist_ok=False)
                scaler=dict(plan['common_scaler']);scaler.update(schema='stage218_reused_common_scaler_v1',
                    reused_scaler=report['common_scaler'],dimension=52,new_scaling=False)
                scaler_b=save_json(str(folder/'scaler.json'),scaler)
                all_new=np.zeros(len(plan['original_ti']),float);all_new[plan['mask']]=plan['weights']
                support_b=save_npz(str(folder/'training_domain_support.npz'),sequence_index=plan['original_ti'],
                    admissible_mask=plan['mask'],old_weight=plan['old_weights'],new_weight=all_new)
                x=old.design(common[ti],plan['common_scaler'])
                if counters['fit_calls_attempted']>=6:raise ValueError('six_fit_budget_exhausted')
                counters['fit_calls_attempted']+=1;checkpoint('fit_attempts.jsonl',scope,cutoff,counters['fit_calls_attempted'])
                def on_complete():
                    counters['fit_calls_completed']+=1;checkpoint('fit_completed.jsonl',scope,cutoff,counters['fit_calls_completed'])
                model,eq,residual=fit_arrays(x,y_all[ti],plan['weights'],on_complete);del x
                model.update(scope=scope,cutoff=cutoff,arm=CANDIDATE,feature_names=old.FEATURE_NAMES,scaler=scaler_b)
                model_b=save_json(str(folder/'portable_model.json'),model);eq_b=save_npz(str(folder/'normal_equations.npz'),**eq)
                records.append(dict(**report,dimension=52,arm=CANDIDATE,scaler=scaler_b,portable_model=model_b,
                    training_domain_support=support_b,normal_equations=eq_b,normal_equation_max_abs_residual=residual))
                models.append(model)
                print(json.dumps(dict(phase='fit_saved_no_forecast',scope=scope,cutoff=cutoff,completed=counters['fit_calls_completed'])),flush=True)
            return models
        models=gated_fits(preflight,do_all_fits)
        if models is None:return finish(False,'all_six_support_required_zero_fit')
        if counters['fit_calls_attempted']!=6 or counters['fit_calls_completed']!=6:raise ValueError('six_fit_completion_required')
        roles['fit_records']=save_json('fit_records.json',records)
        forward,identity=forward_and_select(a,m,common,calendar,plans,models,auth['input_bindings'],counters,save_json,save_csv)
        roles.update(forward);return finish(identity['cash_eligible'],identity['reason'])
    except BaseException as error:
        if not (output/'terminal.json').exists():
            shared.write_json(output/'terminal.json',dict(schema='stage218_terminal_v1',status='failed',exit_code=1,
                counters=counters,actual_fit_calls_attempted=counters['fit_calls_attempted'],actual_fit_calls_completed=counters['fit_calls_completed'],
                cash_eligible=False,elapsed_seconds=time.monotonic()-started,error_type=type(error).__name__,error=str(error),
                traceback=traceback.format_exc(),automatic_retry=False))
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--actual',action='store_true',required=True)
    p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--output',type=Path,default=OUTPUT);args=p.parse_args(argv)
    output,auth,binding,protocol=authorize(args);result=run_actual(output,auth,binding,protocol)
    print(json.dumps(dict(status=result['status'],cash_eligible=result['cash_eligible'],counters=result['counters'],output=str(output))),flush=True)


if __name__=='__main__':main()
