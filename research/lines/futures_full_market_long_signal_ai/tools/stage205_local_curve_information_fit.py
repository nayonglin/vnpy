"""Stage204 fixed COMMON52 + one local-curve q Ridge; root-only actual launch.

All six fits and the strict cheap-direction gate precede every forward score and
selection. Accepted old large artifacts inherit SHA/size and pre/post stat;
imports and tiny fixtures do not read research data or run physical fits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL = LINE/'outputs/stage204_local_curve_information_protocol/protocol.json'
PROTOCOL_SHA = 'b3a950dfb96333457f6a78f89796e07827a5758d0006eb43f71fad3cffd276ca'
OUTPUT = LINE/'outputs/stage205_local_curve_information_fit/actual_run1'
SCOPES = ('main', 'holdout_0', 'holdout_1')
CUTOFFS = ('2020-01-01', '2023-01-01')
END = '2026-10-16'
CANDIDATE, CONTROL = 'CURVE53', 'COMMON52'
PARAMETERS = dict(alpha=1., fit_intercept=True, solver='cholesky')
_HELPERS = None
# Original labels and aliases needed for mature-fold, parent and held checks only.
ACTION_FIELDS = ['sequence_index','event_id','action_sequence_index','action_id',
    'mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index',
    'reference_epoch','actual_epoch','anchor_epoch','u_action_eligible','entry_index',
    'exit_index','label_known_date','label_state','net_R_stress','participation_state']
NUMERIC = ['sequence_index','action_sequence_index','mother_sequence_index','u_index',
           'u_action_eligible','entry_index','exit_index','net_R_stress']
TRAIN_MATCH_FIELDS = [c for c in ACTION_FIELDS if c != 'participation_state']
CHILD_FIELDS = ['sequence_index','action_id','mother_sequence_index','mother_event_id',
    'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']


def helpers():
    global _HELPERS
    if _HELPERS is None:
        modules = []
        for name in ('stage130_contract_choice_fit', 'stage156_voluntary_choices'):
            spec = importlib.util.spec_from_file_location('stage205_'+name, TOOLS/(name+'.py'))
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            modules.append(module)
        _HELPERS = tuple(modules)
    return _HELPERS


def file_binding(path):
    p = Path(path).resolve(); h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return dict(path=str(p), bytes=p.stat().st_size, sha256=h.hexdigest())


def read_bound(bound):
    raw = Path(bound['path']).read_bytes()
    if len(raw) != bound['bytes'] or hashlib.sha256(raw).hexdigest() != bound['sha256']:
        raise ValueError('small_binding_changed '+bound['path'])
    return raw


def same_binding(a, b):
    return all(a.get(k) == b.get(k) for k in ('path','bytes','sha256'))


def source_bundle():
    return sorted([file_binding(TOOLS/name) for name in (
        'stage205_local_curve_information_fit.py','test_stage205_local_curve_information_fit.py',
        'stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py',
        'stage156_voluntary_choices.py')], key=lambda b:b['path'])


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush()


def inherited_stat(bound):
    p = Path(bound['path']); s = p.stat()
    if not p.is_file() or s.st_size != bound['bytes']:
        raise ValueError('inherited_size_differs '+str(p))
    return dict(path=str(p.resolve()),bytes=s.st_size,device=s.st_dev,inode=s.st_ino,
                mtime_ns=s.st_mtime_ns,inherited_sha256=bound['sha256'],rehashed=False)


def q_statistics(q, weights):
    q, weights = np.asarray(q,float), np.asarray(weights,float)
    if q.ndim != 1 or q.shape != weights.shape or not np.isfinite(weights).all() or (weights<=0).any():
        raise ValueError('invalid_q_training_weight_identity')
    finite = np.isfinite(q); mean = var = None
    if finite.any():
        mean = float(np.average(q[finite],weights=weights[finite]))
        var = float(np.average((q[finite]-mean)**2,weights=weights[finite]))
    ready = bool(mean is not None and np.isfinite(mean) and np.isfinite(var) and var>0)
    return dict(ready=ready,reason='' if ready else 'finite_positive_train_q_variance_required',
                training_rows=len(q),finite_count=int(finite.sum()),missing_count=int((~finite).sum()),
                finite_weight_sum=float(weights[finite].sum()),missing_weight_sum=float(weights[~finite].sum()),
                mean=mean if mean is not None and np.isfinite(mean) else None,
                var=var if var is not None and np.isfinite(var) else None,
                scale=float(np.sqrt(var)) if ready else None,
                raw_finite_min=float(q[finite].min()) if finite.any() else None,
                raw_finite_max=float(q[finite].max()) if finite.any() else None)


def design53(raw_common, q, common_scaler, q_stat):
    if not q_stat['ready']: raise ValueError('q_support_not_ready')
    old, _ = helpers(); base = old.design(raw_common,common_scaler)
    q = np.asarray(q,float)
    if q.shape != (len(base),): raise ValueError('q_design_identity_mismatch')
    scalar = np.zeros(len(q),dtype=float); finite = np.isfinite(q)
    scalar[finite] = (q[finite]-q_stat['mean'])/q_stat['scale']
    result = np.column_stack((base,scalar))
    if result.shape != (len(q),53) or not np.isfinite(result).all():
        raise ValueError('invalid53_design')
    return result


def strict_direction_gate(records):
    identities = [(r['scope'],r['cutoff']) for r in records]
    complete = len(identities)==6 and set(identities)=={(s,c) for s in SCOPES for c in CUTOFFS}
    outcomes = []
    for r in records:
        coefficient = float(r['q_coefficient']) if r['q_coefficient'] is not None else float('nan')
        outcomes.append(dict(scope=r['scope'],cutoff=r['cutoff'],
            q_coefficient=coefficient if np.isfinite(coefficient) else None,
            strictly_negative=bool(np.isfinite(coefficient) and coefficient<0)))
    passed = complete and all(r['strictly_negative'] for r in outcomes)
    return dict(schema='stage205_all_six_cheap_direction_gate_v1',passed=passed,
        exact_six_unique_models=complete,outcomes=outcomes,
        rule='all six standardized q coefficients strictly <0 before any forward prediction or selection',
        rejection_status='completed_hypothesis_rejected',sign_reversal_or_refit_permitted=False)


def gated_forward(records, callback):
    """One central call site makes the six-model gate dominate all forward I/O."""
    gate = strict_direction_gate(records)
    return gate, callback() if gate['passed'] else None


def load_inputs(inputs,counters):
    old, _ = helpers()
    small = {name:json.loads(read_bound(inputs[name])) for name in (
        'dataset_manifest','dataset_terminal','geometry_manifest','geometry_review',
        'geometry_decision','control_fit_manifest','control_fit_records','market_protocol')}
    if small['dataset_manifest'].get('status')!='completed' or small['dataset_terminal'].get('status')!='completed':
        raise ValueError('original129_incomplete')
    for role in ('actions','common','mothers'):
        if not same_binding(small['dataset_manifest'].get(role,{}),inputs[role]):
            raise ValueError('original129_binding_'+role)
    if (small['geometry_manifest'].get('schema')!='stage201_projection_manifest_v1'
            or small['geometry_manifest'].get('status')!='completed'
            or small['geometry_review'].get('core_blockers')!=0
            or small['geometry_review'].get('verdict')!='source_geometry_qualification_accepted_only'
            or not same_binding(small['geometry_review'].get('actual_manifest',{}),inputs['geometry_manifest'])
            or small['geometry_decision'].get('status')!='accepted_pure_X_geometry_only'
            or not any(same_binding(b,inputs['q_vector']) for b in small['geometry_manifest'].get('artifacts',[]))):
        raise ValueError('accepted201_202_203_lineage_differs')
    for role in ('actions','mothers'):
        if not same_binding(small['geometry_manifest']['input_bindings'].get(role,{}),inputs[role]):
            raise ValueError('q_original_identity_'+role)
    fit = small['control_fit_manifest']; records = small['control_fit_records']
    if (fit.get('status')!='completed' or fit.get('actual_fit_calls_attempted')!=6
            or fit.get('actual_fit_calls_completed')!=6
            or not same_binding(fit.get('fit_records',{}),inputs['control_fit_records'])):
        raise ValueError('accepted130_fit_identity_differs')
    for role in ('actions','common','mothers','dataset_manifest','dataset_terminal'):
        if not same_binding(fit['input_bindings'].get(role,{}),inputs[role]):
            raise ValueError('accepted130_original_binding_'+role)
    if not same_binding(small['market_protocol']['calendar'],inputs['calendar']):
        raise ValueError('original_source_calendar_differs')
    inherited = {r:inputs[r] for r in ('actions','mothers','common','q_vector')}
    for record in records:
        key = record['scope']+'/'+record['cutoff']
        inherited['training_weights/'+key] = record['training_identity_weights']
    before = {r:inherited_stat(b) for r,b in inherited.items()}
    counters['action_csv_reads'] += 1
    a = pd.read_csv(inputs['actions']['path'],usecols=ACTION_FIELDS,dtype=str,
                    keep_default_na=False,float_precision='round_trip')
    for field in NUMERIC: a[field] = pd.to_numeric(a[field],errors='coerce')
    counters['mother_csv_reads'] += 1
    m = pd.read_csv(inputs['mothers']['path'],usecols=old.IDENTITY,dtype=str,keep_default_na=False)
    for field in ('sequence_index','u_index'): m[field] = pd.to_numeric(m[field],errors='raise')
    if len(m)!=399252 or m.event_id.duplicated().any() or not np.array_equal(m.sequence_index,np.arange(len(m))):
        raise ValueError('full_original_mother_identity_differs')
    if (len(a)!=1552456 or a.action_id.duplicated().any()
            or not np.array_equal(a.sequence_index,np.arange(len(a)))
            or not a.sequence_index.eq(a.action_sequence_index).all()
            or not a.event_id.eq(a.action_id).all() or not a.reference_epoch.eq(a.actual_epoch).all()):
        raise ValueError('full_original_action_identity_differs')
    pi = a.mother_sequence_index.to_numpy(np.int64)
    if (pi<0).any() or (pi>=len(m)).any(): raise ValueError('invalid_parent_sequence')
    for left,right in [('mother_event_id','event_id'),('product_id','product_id'),('family_id','family_id'),
                       ('u_date','u_date'),('u_index','u_index'),('anchor_epoch','reference_epoch')]:
        if not np.array_equal(a[left].to_numpy(),m[right].to_numpy()[pi]):
            raise ValueError('original_parent_child_'+left)
    if not a.u_action_eligible.isin([0,1]).all(): raise ValueError('original_eligibility_differs')
    counters['common_npz_reads'] += 1
    with np.load(inputs['common']['path'],allow_pickle=False) as data:
        if data['columns'].tolist()!=old.COMMON or data['common'].shape!=(len(a),26):
            raise ValueError('original_common_shape_differs')
        common = data['common'].astype(float)
    counters['q_npz_reads'] += 1
    with np.load(inputs['q_vector']['path'],allow_pickle=False) as data:
        if (set(data.files)!={'q_raw','sequence_index'}
                or not np.array_equal(data['sequence_index'],a.sequence_index.to_numpy())):
            raise ValueError('accepted201_q_action_sequence_differs')
        q = np.asarray(data['q_raw'],float)
    if q.shape!=(len(a),) or np.isinf(q).any(): raise ValueError('accepted201_q_domain_differs')
    cal = np.load(io.BytesIO(read_bound(inputs['calendar'])),allow_pickle=False)
    calendar = ([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in cal]
                if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
    if len(calendar)!=5587 or calendar!=sorted(set(calendar)): raise ValueError('calendar_domain_differs')
    return a,m,common,q,calendar,records,inherited,before


def parse_cached_numeric(frame):
    # These are already-parsed130 values exported with17g, so restore IEEE floats
    # directly; a second pd.to_numeric can shift the accepted target/weights.
    for field in NUMERIC+['sample_weight']:
        frame[field] = frame[field].astype(float)
    return frame


def prepare_folds(actions,mothers,common,q,records,counters):
    old, _ = helpers(); plans = []; reports = []
    by_fold = {(r['scope'],r['cutoff']):r for r in records}
    if len(records)!=6 or set(by_fold)!={(s,c) for s in SCOPES for c in CUTOFFS}:
        raise ValueError('accepted130_six_fold_identity_differs')
    for scope in SCOPES:
        for j,cutoff in enumerate(CUTOFFS):
            record = by_fold[(scope,cutoff)]
            train,pred,parent = old.fold_slices(actions,mothers,cutoff,CUTOFFS[j+1] if j+1<len(CUTOFFS) else None,scope)
            # One read of each accepted table; never regenerate family-u weights.
            counters['training_weight_csv_reads'] += 1
            cached = pd.read_csv(record['training_identity_weights']['path'],usecols=TRAIN_MATCH_FIELDS+['sample_weight'],
                                 dtype=str,keep_default_na=False,float_precision='round_trip')
            parse_cached_numeric(cached)
            if len(cached)!=len(train) or len(train)!=record['training_rows']:
                raise ValueError('accepted130_training_row_count_differs')
            for field in TRAIN_MATCH_FIELDS:
                left,right=cached[field].to_numpy(),train[field].to_numpy()
                matched=np.array_equal(left,right,equal_nan=True) if field in NUMERIC else np.array_equal(left,right)
                if not matched:
                    raise ValueError('accepted130_training_identity_differs '+scope+' '+cutoff+' '+field)
            w = cached.sample_weight.to_numpy(float)
            if not np.isfinite(w).all() or (w<=0).any(): raise ValueError('accepted130_weights_invalid')
            ti = train.sequence_index.to_numpy(np.int64)
            scaler = json.loads(read_bound(record['scaler']))
            if (scaler.get('scope')!=scope or scaler.get('cutoff')!=cutoff
                    or scaler.get('feature_names')!=old.FEATURE_NAMES
                    or scaler.get('common',{}).get('columns')!=old.COMMON):
                raise ValueError('accepted130_common_scaler_identity_differs')
            qs = q_statistics(q[ti],w)
            design_finite=False
            if qs['ready']:
                for start in range(0,len(ti),65536):
                    ii=ti[start:start+65536]
                    design53(common[ii],q[ii],scaler,qs)
                design_finite=True
            report = dict(scope=scope,cutoff=cutoff,training_rows=len(ti),
                training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),
                training_groups=record['training_groups'],prediction_children=len(pred),prediction_mothers=len(parent),
                max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
                q_statistics=qs,full53_train_design_finite=design_finite,training_identity_weights=record['training_identity_weights'],
                weight_groups=record['weight_groups'],common_scaler=record['scaler'],
                control_normal_equations=record['normal_equations'],
                training_identity_match_fields=TRAIN_MATCH_FIELDS,training_weights_recomputed=False)
            if any(report[k]!=record[k] for k in ('training_dates','training_families','prediction_children',
                                                  'prediction_mothers','max_u_date','max_label_known_date')):
                raise ValueError('accepted130_fold_support_differs')
            plans.append(dict(report=report,ti=ti,pi=pred.sequence_index.to_numpy(np.int64),
                              mi=parent.sequence_index.to_numpy(np.int64),weights=w,common_scaler=scaler))
            reports.append(report)
    preflight = dict(schema='stage205_global_train_q_support_v1',ready=all(r['q_statistics']['ready'] and r['full53_train_design_finite'] for r in reports),
                     cells=reports,exact_six_unique_folds=True,all_support_before_any_fit=True)
    return plans,preflight


def fit_arrays(x,y,weights,on_complete):
    old, _ = helpers(); estimator = old.legacy.Ridge(**PARAMETERS)
    with old.legacy.threadpool_limits(limits=1): estimator.fit(x,y,sample_weight=weights)
    on_complete()  # Count the physical fit before subsequent diagnostics/output.
    z = np.column_stack((x,np.ones(len(x))))
    lhs = z.T@(weights[:,None]*z); lhs[np.arange(53),np.arange(53)] += PARAMETERS['alpha']
    rhs = z.T@(weights*y); beta = np.r_[estimator.coef_,estimator.intercept_]
    residual = lhs@beta-rhs
    # Nonfinite q coefficients belong to the hypothesis gate, after all six fits.
    finite_solution = bool(np.isfinite(beta).all())
    if finite_solution and not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):
        raise ValueError('ridge_normal_equations_mismatch')
    portable = dict(schema='stage205_portable_ridge53_v1',parameters=PARAMETERS,
                    coef=[float(v) if np.isfinite(v) else None for v in estimator.coef_],
                    intercept=float(estimator.intercept_) if np.isfinite(estimator.intercept_) else None)
    return portable,dict(lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,
                         weight_sum=np.array(weights.sum())),float(np.max(np.abs(residual))) if finite_solution else None


def choose_scope(mothers,children,scope,arm,calendar):
    _,voluntary = helpers()
    if scope not in SCOPES or not children.scope.eq(scope).all(): raise ValueError('mixed_scope_selection')
    rows = children[voluntary.SCORE_FIELDS].copy(); rows['scope'] = 'main'
    result = voluntary.select_full_pool(mothers.to_dict('records'),rows.to_dict('records'),calendar,END,
                                        audit_sink=lambda row:None)
    chosen = pd.DataFrame(result['choices']); chosen['scope'] = scope; chosen['arm'] = arm
    return chosen,result['boundaries'],result['summary']


def forward_and_select(a,m,common,q,calendar,plans,models,inputs,counters,save_json,save_csv):
    old,voluntary = helpers(); children = []; seen = {True:np.zeros(len(a),bool),False:np.zeros(len(a),bool)}
    for plan,model in zip(plans,models):
        r=plan['report']; pi=plan['pi']; scope=r['scope']; cutoff=r['cutoff']
        counters['prediction_calls_attempted'] += 1
        xp=design53(common[pi],q[pi],plan['common_scaler'],r['q_statistics'])
        scores=xp@np.asarray(model['coef'],float)+model['intercept']
        if not np.isfinite(scores).all(): raise ValueError('nonfinite_forward_score')
        counters['prediction_calls_completed'] += 1; counters['prediction_model_rows'] += len(pi)
        if seen[scope=='main'][pi].any(): raise ValueError('duplicate_forward_child_identity')
        seen[scope=='main'][pi]=True
        child=a.iloc[pi][CHILD_FIELDS].copy(); child['score']=scores
        child['scope']=scope; child['cutoff']=cutoff; child['arm']=CANDIDATE
        child['q_raw']=q[pi]; child['q_missing_diagnostic']=(~np.isfinite(q[pi])).astype(np.int8)
        child['q_design']=xp[:,52]; children.append(child)
        del xp
    expected=a.u_date.ge(CUTOFFS[0]).to_numpy()
    if (counters['prediction_model_rows']!=1933480 or int(expected.sum())!=966740
            or any(not np.array_equal(v,expected) for v in seen.values())):
        raise ValueError('full_forward_child_domain_differs')
    children=pd.concat(children,ignore_index=True)
    choices=[]; boundaries={}; summaries=[]
    for scope in SCOPES:
        part=children.loc[children.scope.eq(scope)]
        mothers=m.loc[m.u_date.ge(CUTOFFS[0])]
        if scope!='main': mothers=mothers.loc[mothers.family_id.map(old.family_group).eq(int(scope[-1]))]
        counters['candidate_selection_calls'] += 1
        chosen,new_bounds,summary=choose_scope(mothers,part,scope,CANDIDATE,calendar)
        choices.append(chosen); summaries.append(dict(arm=CANDIDATE,scope=scope,summary=summary))
        for epoch,value in new_bounds.items():
            if epoch in boundaries and boundaries[epoch]!=value: raise ValueError('shared_K_boundary_differs')
            boundaries[epoch]=value
    choices=pd.concat(choices,ignore_index=True)
    # Frozen130 scores are read once, held rows retained; main is never reselected.
    controls=[]; control_parts=[]; old_rows=0
    for chunk in pd.read_csv(inputs['control_child_scores']['path'],usecols=voluntary.SCORE_FIELDS,
                             dtype=str,keep_default_na=False,float_precision='round_trip',chunksize=200000):
        old_rows+=len(chunk); control_parts.append(chunk.loc[chunk.scope.ne('main')].copy())
    counters['control_score_csv_reads'] += 1
    control_children=pd.concat(control_parts,ignore_index=True)
    if old_rows!=1933480 or len(control_children)!=966740: raise ValueError('accepted130_child_row_counts_differ')
    expected_ids=a.loc[expected,'action_id']
    if control_children.action_id.duplicated().any() or set(control_children.action_id)!=set(expected_ids):
        raise ValueError('accepted130_held_forward_identity_differs')
    for scope in SCOPES[1:]:
        part=control_children.loc[control_children.scope.eq(scope)]
        mothers=m.loc[m.u_date.ge(CUTOFFS[0])&m.family_id.map(old.family_group).eq(int(scope[-1]))]
        counters['control_held_selection_calls'] += 1
        chosen,new_bounds,summary=choose_scope(mothers,part,scope,CONTROL,calendar)
        controls.append(chosen); summaries.append(dict(arm=CONTROL,scope=scope,summary=summary))
        if any(boundaries.get(e)!=b for e,b in new_bounds.items()): raise ValueError('control_held_K_boundary_differs')
    controls=pd.concat(controls,ignore_index=True)
    main=choices.loc[choices.scope.eq('main')].sort_values('sequence_index',kind='stable').reset_index(drop=True)
    held=choices.loc[choices.scope.ne('main')].sort_values('sequence_index',kind='stable').reset_index(drop=True)
    controls=controls.sort_values('sequence_index',kind='stable').reset_index(drop=True)
    expected_parents=set(m.loc[m.u_date.ge(CUTOFFS[0]),'event_id'])
    for name,frame in [('candidate_main',main),('candidate_held',held),('control_held',controls)]:
        if len(frame)!=161014 or frame.event_id.duplicated().any() or set(frame.event_id)!=expected_parents:
            raise ValueError('complete_parent_identity_differs '+name)
    if set(boundaries)!=set(a.loc[expected,'reference_epoch']): raise ValueError('full_epoch_K_domain_differs')
    comparison=pd.concat([controls.assign(arm='A'),held.assign(arm='B')],ignore_index=True)
    diagnostic,daily,_=old.held_diagnostics(comparison,a)
    diagnostic.update(schema='stage205_curve53_held_K_original_target_diagnostic_v1',
        arm_aliases={'A':CONTROL,'B':CANDIDATE},contrast=CANDIDATE+'_minus_'+CONTROL,
        target='unchanged original129 firstexit net_R_stress; not K-truncated outcome',
        numeric_missing_causal_isolation=False,strictPIT_certified=False)
    for group in diagnostic['groups'].values():
        mean=group['known_u_equal_mean_increment_R']; unknown=group['unknown_differential_selected_events']
        group['nominal_pass']=bool(mean is not None and mean>0 and unknown==0)
        group['selected_by_arm']={CONTROL:group['selected_by_arm']['A'],CANDIDATE:group['selected_by_arm']['B']}
    out={role:save_csv(role+'.csv.gz',frame) for role,frame in (
        ('child_scores',children),('choices_main',main),('choices_holdout',held),
        ('control_held_K',controls),('held_daily',daily))}
    out['held_diagnostic']=save_json('held_diagnostic.json',diagnostic)
    out['boundaries']=save_json('boundaries.json',dict(schema='stage205_fixed155_K_boundaries_v1',
        epochs=boundaries,policy_version=voluntary.POLICY_VERSION,sample_end=END,
        calendar=inputs['calendar'],account_deadline_certified=False))
    out['selection_summary']=save_json('selection_summary.json',summaries)
    return out


def authorize(args):
    output=Path(args.output).resolve()
    if output!=OUTPUT or output.exists(): raise ValueError('fresh_exact_stage205_actual_run1_required')
    protocol_binding=file_binding(PROTOCOL)
    if protocol_binding['sha256']!=PROTOCOL_SHA: raise ValueError('frozen204_protocol_differs')
    protocol=json.loads(read_bound(protocol_binding)); auth_binding=file_binding(args.authorization)
    if auth_binding['sha256']!=args.authorization_sha256: raise ValueError('root_binding_sha_differs')
    auth=json.loads(read_bound(auth_binding))
    required=dict(schema='stage204_exact_root_fit_authorization_v1',authorized_by='root',stage='fit',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
    if (any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle()
            or auth.get('input_bindings')!=protocol['input_bindings']):
        raise ValueError('exact_root_source_authorization_differs')
    return output,auth,auth_binding,protocol_binding


def run_actual(output,auth,authorization,protocol_binding):
    output=Path(output); output.mkdir(parents=True,exist_ok=False); started=time.monotonic()
    bundle=source_bundle(); artifacts={}; roles={}; plans=[]; records=[]; evidence={}
    counters=dict(fit_calls_attempted=0,fit_calls_completed=0,old_fit=0,cash=0,old_cash=0,SQL=0,
        source_projection=0,new_labels=0,downloads=0,large_input_hash_scans=0,
        action_csv_reads=0,mother_csv_reads=0,common_npz_reads=0,q_npz_reads=0,
        training_weight_csv_reads=0,training_weights_recomputed=0,control_score_csv_reads=0,
        prediction_calls_attempted=0,prediction_calls_completed=0,prediction_model_rows=0,
        candidate_selection_calls=0,control_held_selection_calls=0,control_main_selection_calls=0)
    def save_json(name,obj):
        write_json(output/name,obj); bound=file_binding(output/name); artifacts[name]=bound; return bound
    def save_csv(name,frame):
        frame.to_csv(output/name,index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
        bound=file_binding(output/name); artifacts[name]=bound; return bound
    def save_npz(name,**values):
        with (output/name).open('xb') as stream: np.savez_compressed(stream,**values)
        bound=file_binding(output/name); artifacts[name]=bound; return bound
    def checkpoint(name,scope,cutoff,count):
        with (output/name).open('a') as stream:
            stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,count=count))+'\n'); stream.flush()
    save_json('started.json',dict(status='started',started_at=datetime.now(timezone.utc).isoformat(),
        protocol=protocol_binding,authorization=authorization,source_bundle=bundle,automatic_retry=False))
    def finish(status,cash_eligible,reason):
        if bundle!=source_bundle(): raise ValueError('source_changed_during_actual')
        if evidence:
            after={r:inherited_stat(b) for r,b in evidence['bindings'].items()}
            evidence['after']=after
            if evidence['before']!=after: raise ValueError('inherited_sources_changed_during_actual')
        for name in ('fit_attempts.jsonl','fit_completed.jsonl'):
            if (output/name).exists(): artifacts[name]=file_binding(output/name)
        summary=dict(status=status,reason=reason,counters=counters,
            actual_fit_calls_attempted=counters['fit_calls_attempted'],actual_fit_calls_completed=counters['fit_calls_completed'],
            actual_model_fit_calls=counters['fit_calls_completed'],new_cash=0,new_SQL=0,
            cumulative_fit=421+counters['fit_calls_completed'],cumulative_cash=226,
            cash_eligible=cash_eligible,goal_complete=False,production_qualified=False,
            numeric_missing_causal_isolation=False,alpha_qualified=False)
        roles['summary']=save_json('summary.json',summary)
        terminal=save_json('terminal.json',dict(**summary,exit_code=0,elapsed_seconds=time.monotonic()-started,automatic_retry=False))
        manifest=dict(schema='stage205_local_curve_information_fit_v1',**summary,
            protocol=protocol_binding,protocol_sha256=PROTOCOL_SHA,source_bundle=bundle,authorization=authorization,
            input_bindings=auth['input_bindings'],source_read_receipt=evidence,artifacts=artifacts.copy(),terminal=terminal,
            prediction_mothers_per_arm=161014 if cash_eligible else 0,
            prediction_children=counters['prediction_model_rows'],
            control_choices_main_reused=auth['input_bindings']['control_choices_main_K'],
            candidate_arm=CANDIDATE,control_arm=CONTROL,
            interpretation='q plus fixed train-mean imputation incremental prediction; no numeric-vs-missing causal isolation',
            **roles)
        write_json(output/'manifest.json',manifest)
        return manifest
    try:
        a,m,common,q,calendar,old_records,inherited,before=load_inputs(auth['input_bindings'],counters)
        evidence=dict(bindings=inherited,before=before)
        plans,preflight=prepare_folds(a,m,common,q,old_records,counters)
        roles['preflight']=save_json('preflight.json',preflight)
        if not preflight['ready']:
            return finish('completed_support_rejected',False,'all_six_positive_finite_train_q_variances_required')
        models=[]; y_all=a.net_R_stress.to_numpy(float)
        old,_=helpers()
        for plan in plans:
            report=plan['report']; scope=report['scope']; cutoff=report['cutoff']; ti=plan['ti']
            folder=Path('folds')/scope/cutoff; (output/folder).mkdir(parents=True,exist_ok=False)
            scaler=dict(common=plan['common_scaler']['common'],q=report['q_statistics'],scope=scope,cutoff=cutoff,
                feature_names=old.FEATURE_NAMES+['local_curve_q_standardized'],dimension=53,
                common_scaler_reused=report['common_scaler'],new_missing_input=False,
                q_missing_design='exact0',q_statistic_scope='this_fold_finite_q_original_train_weights_only')
            scaler_b=save_json(str(folder/'scaler.json'),scaler)
            support_b=save_npz(str(folder/'training_q_support.npz'),sequence_index=ti,q_raw=q[ti])
            x=design53(common[ti],q[ti],plan['common_scaler'],report['q_statistics'])
            if counters['fit_calls_attempted']>=6: raise ValueError('six_fit_budget_exhausted')
            counters['fit_calls_attempted']+=1
            checkpoint('fit_attempts.jsonl',scope,cutoff,counters['fit_calls_attempted'])
            def on_complete():
                counters['fit_calls_completed']+=1
                checkpoint('fit_completed.jsonl',scope,cutoff,counters['fit_calls_completed'])
            model,eq,residual=fit_arrays(x,y_all[ti],plan['weights'],on_complete); del x
            model.update(scope=scope,cutoff=cutoff,arm=CANDIDATE,feature_names=scaler['feature_names'],scaler=scaler_b)
            model_b=save_json(str(folder/'portable_model.json'),model)
            eq_b=save_npz(str(folder/'normal_equations.npz'),**eq)
            coefficient=float(eq['coefficient_with_intercept'][52])
            records.append(dict(**report,dimension=53,arm=CANDIDATE,scaler=scaler_b,portable_model=model_b,
                training_q_support=support_b,normal_equations=eq_b,normal_equation_max_abs_residual=residual,
                q_coefficient=coefficient if np.isfinite(coefficient) else None,
                q_coefficient_finite=bool(np.isfinite(coefficient)),
                q_strictly_negative=bool(np.isfinite(coefficient) and coefficient<0)))
            models.append(model)
            print(json.dumps(dict(phase='fit_saved_no_forecast',scope=scope,cutoff=cutoff,
                                 completed=counters['fit_calls_completed'])),flush=True)
        if counters['fit_calls_attempted']!=6 or counters['fit_calls_completed']!=6: raise ValueError('six_fit_completion_required')
        roles['fit_records']=save_json('fit_records.json',records)
        # Save the gate first; no candidate/control prediction/selection can precede it.
        gate=strict_direction_gate(records); roles['direction_gate']=save_json('direction_gate.json',gate)
        if not gate['passed']:
            return finish('completed_hypothesis_rejected',False,'cheap_direction_not_strictly_supported_in_all_six_models')
        for role in ('control_child_scores','control_choices_main_K'):
            evidence['bindings'][role]=auth['input_bindings'][role]
            evidence['before'][role]=inherited_stat(auth['input_bindings'][role])
        gate,forward=gated_forward(records,lambda:forward_and_select(a,m,common,q,calendar,plans,models,
                                    auth['input_bindings'],counters,save_json,save_csv))
        roles.update(forward)
        return finish('completed',True,'six_direction_gate_passed_full_forward_selection_complete')
    except BaseException as error:
        if not (output/'terminal.json').exists():
            write_json(output/'terminal.json',dict(schema='stage205_terminal_v1',status='failed',exit_code=1,
                counters=counters,actual_fit_calls_attempted=counters['fit_calls_attempted'],
                actual_fit_calls_completed=counters['fit_calls_completed'],cash_eligible=False,
                elapsed_seconds=time.monotonic()-started,error_type=type(error).__name__,error=str(error),
                traceback=traceback.format_exc(),automatic_retry=False))
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--actual',action='store_true',required=True)
    p.add_argument('--authorization',required=True); p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--output',type=Path,default=OUTPUT)
    args=p.parse_args(argv); output,auth,binding,protocol=authorize(args)
    result=run_actual(output,auth,binding,protocol)
    print(json.dumps(dict(status=result['status'],cash_eligible=result['cash_eligible'],
                         counters=result['counters'],output=str(output))),flush=True)


if __name__=='__main__': main()
