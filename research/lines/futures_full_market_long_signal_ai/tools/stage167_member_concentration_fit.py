"""Frozen166 two-arm54 Ridge with full-domain unchanged156 voluntary selection.

Import reads no research data. Actual requires the root's exact-source record and
a fresh output. No old predictions/models, SQL, network, cash or source raw reads.
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
PROTOCOL = LINE/'outputs/stage166_member_concentration_protocol/protocol.json'
PROTOCOL_SHA = 'ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a'
ARMS = ('CONTROL54', 'CONCENTRATION54')
SCOPES = ('main', 'holdout_0', 'holdout_1')
CUTOFFS = ('2020-01-01', '2023-01-01')
END = '2026-10-16'
PARAMETERS = dict(alpha=1., fit_intercept=True, solver='cholesky')
INPUT_ROLES = ('execution_protocol', 'voluntary_protocol', 'dataset_manifest', 'actions', 'common',
               'mothers', 'dataset_terminal', 'member_manifest', 'member_projection',
               'member_review_receipt', 'source_acceptance', 'calendar', 'market_protocol')
PROJECTION_ID = ('action_sequence_index', 'action_id', 'actual_epoch', 'u_date', 'u_index',
                 'product_id', 'family_id', 'mother_sequence_index', 'mother_event_id')
_HELPERS = None


def helpers():
    global _HELPERS
    if _HELPERS is None:
        loaded = []
        for name in ('stage130_contract_choice_fit', 'stage156_voluntary_choices'):
            spec = importlib.util.spec_from_file_location('stage167_'+name, TOOLS/(name+'.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            loaded.append(module)
        _HELPERS = tuple(loaded)
    return _HELPERS


def file_binding(path):
    p = Path(path); digest = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=digest.hexdigest())


def same_binding(a, b):
    return all(a.get(key) == b.get(key) for key in ('path', 'bytes', 'sha256'))


def read_bound(b):
    data = Path(b['path']).read_bytes()
    if len(data) != b['bytes'] or hashlib.sha256(data).hexdigest() != b['sha256']:
        raise ValueError('input_binding_changed '+b['path'])
    return data


def write_json(path, obj):
    with Path(path).open('x') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def stat_identity(path):
    p = Path(path); s = p.stat()
    return dict(path=str(p.resolve()), bytes=s.st_size, mtime_ns=s.st_mtime_ns, inode=s.st_ino)


def source_bundle():
    return sorted([file_binding(TOOLS/name) for name in (
        'stage167_member_concentration_fit.py', 'test_stage167_member_concentration_fit.py',
        'stage130_contract_choice_fit.py', 'stage071_settlement_narrow_fit.py',
        'stage156_voluntary_choices.py')], key=lambda b: b['path'])


def q_statistics(q, weights):
    q, weights = np.asarray(q, float), np.asarray(weights, float)
    if q.shape != weights.shape or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('invalid_q_weight_identity')
    mask = np.isfinite(q)
    if not mask.any():
        return dict(ready=False, reason='no_finite_q', finite_count=0, finite_weight_sum=0.,
                    mean=None, var=None, scale=None)
    mean = float(np.average(q[mask], weights=weights[mask]))
    var = float(np.average((q[mask]-mean)**2, weights=weights[mask]))
    ready = bool(np.isfinite(mean) and np.isfinite(var) and var > 0)
    return dict(ready=ready, reason='' if ready else 'nonpositive_q_variance', finite_count=int(mask.sum()),
                finite_weight_sum=float(weights[mask].sum()), mean=mean, var=var,
                scale=float(np.sqrt(var)) if ready else None)


def global_preflight(cells):
    failures = [dict(scope=c['scope'], cutoff=c['cutoff'], reason=c['q_statistics']['reason'])
                for c in cells if not c['q_statistics']['ready']]
    ready = len(cells) == 6 and not failures
    return dict(schema='stage167_global_preflight_v1', ready=ready, cells=cells, failures=failures,
                fit_calls_authorized=12 if ready else 0,
                meaning='all six original mature-fold source supports checked before any fit')


def design54(raw_common, q, common_scaler, q_stat, arm):
    if arm not in ARMS or not q_stat['ready']:
        raise ValueError('nonready_or_unknown_design')
    old, _ = helpers()
    base = old.design(raw_common, common_scaler)
    q = np.asarray(q, float)
    if len(q) != len(base):
        raise ValueError('q_design_identity_mismatch')
    finite = np.isfinite(q)
    scalar = np.where(finite, (q-q_stat['mean'])/q_stat['scale'], 0.) if arm == ARMS[1] else np.zeros(len(q))
    result = np.column_stack((base, (~finite).astype(float), scalar))
    if result.shape != (len(q),54) or not np.isfinite(result).all():
        raise ValueError('invalid54_design')
    return result


def align_projection(actions, projection):
    if len(actions) != len(projection):
        raise ValueError('projection_identity_length')
    for field in PROJECTION_ID:
        left, right = actions[field].to_numpy(), projection[field].to_numpy()
        if field in ('action_sequence_index', 'mother_sequence_index', 'u_index'):
            right = pd.to_numeric(projection[field], errors='raise').to_numpy()
        if not np.array_equal(left, right):
            raise ValueError('projection_identity_'+field)
    q = pd.to_numeric(projection.scalar_primary, errors='coerce').to_numpy(float)
    text = projection.missing.astype(str).str.lower()
    if not text.isin(['true','false']).all():
        raise ValueError('invalid_member_missing_flag')
    missing = text.eq('true').to_numpy()
    observed = projection.projection_status.eq('observed').to_numpy()
    if not np.array_equal(~missing, np.isfinite(q)) or not np.array_equal(observed, ~missing):
        raise ValueError('member_q_missing_or_observed_mismatch')
    return q


def choose_scope(mothers, child_scores, scope, arm, calendar):
    old, voluntary = helpers()
    if scope not in SCOPES or arm not in ARMS or not child_scores.scope.eq(scope).all():
        raise ValueError('mixed_scope_selection')
    rows = child_scores[voluntary.SCORE_FIELDS].copy()
    rows['scope'] = 'main'  #156 is a pure main-only helper; this call is one scope.
    result = voluntary.select_full_pool(mothers.to_dict('records'), rows.to_dict('records'), calendar, END,
                                       audit_sink=lambda audit: None)
    choices = pd.DataFrame(result['choices'])
    choices['scope'], choices['arm'] = scope, arm
    return choices, result['boundaries'], result['summary']


def restore_parent_order(frame):
    return frame.sort_values(['arm','sequence_index'],kind='stable').reset_index(drop=True)


def fit_arrays(x, y, weights, on_completed=None):
    old, _ = helpers()
    estimator = old.legacy.Ridge(**PARAMETERS)
    with old.legacy.threadpool_limits(limits=1):
        estimator.fit(x, y, sample_weight=weights)
    if on_completed is not None:
        on_completed()  # Record the physical fit before any equation/output check.
    z = np.column_stack((x, np.ones(len(x))))
    lhs = z.T@(weights[:,None]*z)
    lhs[np.arange(54), np.arange(54)] += PARAMETERS['alpha']
    rhs = z.T@(weights*y)
    beta = np.r_[estimator.coef_, estimator.intercept_]
    if not np.allclose(lhs@beta, rhs, rtol=1e-8, atol=1e-7):
        raise ValueError('ridge_normal_equations_mismatch')
    portable = dict(schema='stage167_portable_ridge54_v1', parameters=PARAMETERS,
                    coef=estimator.coef_.tolist(), intercept=float(estimator.intercept_))
    return estimator, portable, dict(lhs=lhs, rhs=rhs, coefficient_with_intercept=beta,
                                     weight_sum=np.array(weights.sum()))


def load_inputs(inputs):
    old, _ = helpers()
    small = {role: json.loads(read_bound(inputs[role])) for role in INPUT_ROLES
             if role not in ('actions','common','mothers','member_projection','calendar')}
    if small['dataset_manifest'].get('status') != 'completed' or small['dataset_terminal'].get('status') != 'completed':
        raise ValueError('accepted129_not_complete')
    for role in ('actions','common','mothers'):
        if not same_binding(small['dataset_manifest'][role], inputs[role]):
            raise ValueError('accepted129_role_binding_mismatch')
    accepted = small['source_acceptance']
    if (not accepted.get('source_measurement_arithmetic_accepted')
            or not same_binding(accepted['source_manifest'], inputs['member_manifest'])
            or not same_binding(accepted['independent_review'], inputs['member_review_receipt'])):
        raise ValueError('source165_acceptance_closure_mismatch')
    member_projection = next((b for b in small['member_manifest']['artifacts']
                              if b['role'] == 'actions_projection'), {})
    if not same_binding(member_projection, inputs['member_projection']):
        raise ValueError('accepted162_projection_binding_mismatch')
    if not same_binding(small['market_protocol']['calendar'], inputs['calendar']):
        raise ValueError('accepted052_calendar_binding_mismatch')
    evidence = {}
    for role in ('actions','common','mothers','member_projection'):
        evidence[role] = dict(binding=inputs[role], stat_before=stat_identity(inputs[role]['path']),
                              verification='accepted129_or162_sha_inherited_single_data_read')
        if evidence[role]['stat_before']['bytes'] != inputs[role]['bytes']:
            raise ValueError('accepted_data_size_mismatch '+role)
    a = pd.read_csv(inputs['actions']['path'], usecols=old.ACTION_COLUMNS, dtype=str, keep_default_na=False,
                    float_precision='round_trip')
    for field in old.NUMERIC:
        a[field] = pd.to_numeric(a[field], errors='coerce')
    m = pd.read_csv(inputs['mothers']['path'], usecols=old.IDENTITY, dtype=str, keep_default_na=False)
    for field in ('sequence_index','u_index'):
        m[field] = pd.to_numeric(m[field], errors='raise')
    if len(m) != 399252 or not np.array_equal(m.sequence_index, np.arange(len(m))) or m.event_id.duplicated().any():
        raise ValueError('full_mother_identity_mismatch')
    if (len(a) != 1552456 or a.action_id.duplicated().any() or not np.array_equal(a.sequence_index,np.arange(len(a)))
            or not a.sequence_index.eq(a.action_sequence_index).all() or not a.event_id.eq(a.action_id).all()
            or not a.reference_epoch.eq(a.actual_epoch).all()):
        raise ValueError('full_action_identity_mismatch')
    parent_index = a.mother_sequence_index.to_numpy(np.int64)
    if (parent_index < 0).any() or (parent_index >= len(m)).any():
        raise ValueError('action_parent_outside_domain')
    for left, right in [('mother_event_id','event_id'), ('product_id','product_id'), ('family_id','family_id'),
                        ('u_date','u_date'), ('u_index','u_index'), ('anchor_epoch','reference_epoch')]:
        if not np.array_equal(a[left].to_numpy(),m[right].to_numpy()[parent_index]):
            raise ValueError('action_parent_identity_'+left)
    if not a.u_action_eligible.isin([0,1]).all():
        raise ValueError('invalid_original_eligibility')
    fields = list(PROJECTION_ID)+['scalar_primary','missing','projection_status']
    p = pd.read_csv(inputs['member_projection']['path'], usecols=fields, dtype=str, keep_default_na=False,
                    float_precision='round_trip')
    q = align_projection(a,p); del p
    with np.load(inputs['common']['path'],allow_pickle=False) as archive:
        if archive['columns'].tolist() != old.COMMON or archive['common'].shape != (len(a),26):
            raise ValueError('accepted_common_shape_columns_mismatch')
        common = archive['common'].astype(float)
    cal_array = np.load(io.BytesIO(read_bound(inputs['calendar'])),allow_pickle=False)
    calendar = ([str(int(day))[:4]+'-'+str(int(day))[4:6]+'-'+str(int(day))[6:8] for day in cal_array]
                if cal_array.dtype.kind in 'iu' else cal_array.astype('datetime64[D]').astype(str).tolist())
    if len(calendar) != 5587 or calendar != sorted(set(calendar)):
        raise ValueError('full052_calendar_mismatch')
    for role, state in evidence.items():
        state['stat_after'] = stat_identity(inputs[role]['path'])
        if state['stat_before'] != state['stat_after']:
            raise ValueError('accepted_input_changed_while_reading '+role)
    return a,m,common,q,calendar,evidence


def prepare_folds(actions, mothers, common, q):
    old, _ = helpers()
    plans, support = [], []
    for scope in SCOPES:
        for j, cutoff in enumerate(CUTOFFS):
            nxt = CUTOFFS[j+1] if j+1 < len(CUTOFFS) else None
            train,pred,parent = old.fold_slices(actions,mothers,cutoff,nxt,scope)
            ti = train.sequence_index.to_numpy(int); pi = pred.sequence_index.to_numpy(int)
            mi = parent.sequence_index.to_numpy(int)
            weights,groups = old.training_weights(train)
            w = weights.sample_weight.to_numpy(float)
            qstat = q_statistics(q[ti],w)
            stats = [old.legacy.finite_stats(common[ti,k],w) for k in range(26)]
            scaler = dict(common=dict(columns=old.COMMON, **{key:[s[key] for s in stats]
                          for key in ('mean','var','scale','finite_count')}),q=qstat,
                          feature_names=old.FEATURE_NAMES+['member_concentration_missing','member_concentration_standardized'],
                          scope=scope,cutoff=cutoff,control_final_design='exact_constant0',
                          weighting='unchanged130 family_u_interval_union_then_divide_actions_then_equal_u')
            report = dict(scope=scope,cutoff=cutoff,training_rows=len(ti),training_dates=int(train.u_date.nunique()),
                          training_families=int(train.family_id.nunique()),training_groups=len(groups),
                          prediction_children=len(pi),prediction_mothers=len(mi),q_statistics=qstat,
                          max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()))
            support.append(report)
            plans.append(dict(report=report,ti=ti,pi=pi,mi=mi,weights=weights,groups=groups,scaler=scaler))
    return plans, global_preflight(support)


def authorize(args):
    output = Path(args.output).resolve()
    if output.exists() or LINE/'outputs/stage167_member_concentration_fit' not in output.parents:
        raise ValueError('fresh_stage167_output_required')
    protocol_b = file_binding(args.protocol)
    if args.protocol_sha256 != PROTOCOL_SHA or protocol_b['sha256'] != PROTOCOL_SHA:
        raise ValueError('frozen166_protocol_mismatch')
    auth_b = file_binding(args.authorization)
    if auth_b['sha256'] != args.authorization_sha256:
        raise ValueError('root_authorization_hash_mismatch')
    auth = json.loads(read_bound(auth_b))
    required = dict(schema='stage166_exact_root_authorization_v1',authorized_by='root',stage='fit',
                    exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
    protocol = json.loads(read_bound(protocol_b))
    expected = {role:protocol['source_bindings'][role] for role in INPUT_ROLES}
    if (any(auth.get(key) != value for key,value in required.items()) or auth.get('source_bundle') != source_bundle()
            or auth.get('input_bindings') != expected):
        raise ValueError('exact_root_fit_authorization_mismatch')
    return output,auth,auth_b,protocol_b


def run_actual(output, auth, authorization, protocol_binding):
    output.mkdir(parents=True,exist_ok=False)
    started = time.monotonic(); bundle = source_bundle(); attempts = completed = 0
    bindings = {}
    def save_json(name,obj):
        write_json(output/name,obj); b=file_binding(output/name);bindings[name]=b;return b
    def save_csv(name,frame):
        frame.to_csv(output/name,index=False,float_format='%.17g');b=file_binding(output/name);bindings[name]=b;return b
    def checkpoint(name,arm,scope,cutoff,count):
        with (output/name).open('a') as stream:
            stream.write(json.dumps(dict(arm=arm,scope=scope,cutoff=cutoff,count=count))+'\n');stream.flush()
    save_json('started.json',dict(status='started',stage='fit',started_at=datetime.now(timezone.utc).isoformat(),
              protocol=protocol_binding,authorization=authorization,source_bundle=bundle,automatic_retry=False))
    try:
        a,m,common,q,calendar,input_evidence = load_inputs(auth['input_bindings'])
        plans,preflight = prepare_folds(a,m,common,q)
        preflight_b = save_json('preflight.json',preflight)
        if not preflight['ready']:
            terminal = save_json('terminal.json',dict(status='no_go',exit_code=0,actual_fit_calls_attempted=0,
                      actual_fit_calls_completed=0,reason='global_q_support_preflight_failed',elapsed_seconds=time.monotonic()-started,
                      new_cash=0,new_SQL=0,downloads=0,automatic_retry=False))
            save_json('manifest.json',dict(schema='stage167_member_concentration_fit_v1',status='no_go',cash_eligible=False,
                      actual_model_fit_calls=0,actual_fit_calls_attempted=0,actual_fit_calls_completed=0,
                      protocol=protocol_binding,protocol_sha256=PROTOCOL_SHA,source_bundle=bundle,authorization=authorization,
                      input_bindings=auth['input_bindings'],input_evidence=input_evidence,preflight=preflight_b,terminal=terminal))
            return
        old,voluntary = helpers()
        choices,records,selection_summaries,boundaries = [],[],[],{}
        score_count=0
        score_seen={(arm,is_main):np.zeros(len(a),dtype=bool) for arm in ARMS for is_main in (True,False)}
        for plan in plans:
            report=plan['report'];scope,cutoff=report['scope'],report['cutoff']
            fold=output/'folds'/scope/cutoff;fold.mkdir(parents=True,exist_ok=False)
            train=a.iloc[plan['ti']].copy().reset_index(drop=True)
            train['member_q_raw']=q[plan['ti']];train['member_q_missing']=(~np.isfinite(q[plan['ti']])).astype(int)
            for column in plan['weights']:
                train[column]=plan['weights'][column].to_numpy()
            train_b=save_csv(str(fold.relative_to(output)/'training_identity_weights.csv.gz'),train)
            group_b=save_csv(str(fold.relative_to(output)/'weight_groups.csv.gz'),plan['groups'])
            scaler_b=save_json(str(fold.relative_to(output)/'scaler.json'),plan['scaler'])
            weights=plan['weights'].sample_weight.to_numpy(float)
            y=a.net_R_stress.to_numpy(float)[plan['ti']]
            pred=a.iloc[plan['pi']];parent=m.iloc[plan['mi']]
            for arm in ARMS:
                directory=fold/arm;directory.mkdir(exist_ok=False)
                x=design54(common[plan['ti']],q[plan['ti']],plan['scaler'],plan['report']['q_statistics'],arm)
                attempts+=1;checkpoint('fit_attempts.jsonl',arm,scope,cutoff,attempts)
                def completed_fit():
                    nonlocal completed
                    completed+=1;checkpoint('fit_completed.jsonl',arm,scope,cutoff,completed)
                estimator,portable,eq=fit_arrays(x,y,weights,on_completed=completed_fit)
                portable.update(scope=scope,cutoff=cutoff,arm=arm,feature_names=plan['scaler']['feature_names'],scaler=scaler_b)
                portable_b=save_json(str(directory.relative_to(output)/'portable_model.json'),portable)
                eq_path=directory/'normal_equations.npz'
                with eq_path.open('xb') as stream:
                    np.savez_compressed(stream,**eq)
                eq_b=file_binding(eq_path);bindings[str(eq_path.relative_to(output))]=eq_b
                del x
                xp=design54(common[plan['pi']],q[plan['pi']],plan['scaler'],plan['report']['q_statistics'],arm)
                scores=estimator.predict(xp)
                if not np.isfinite(scores).all() or not np.allclose(scores,xp@np.asarray(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):
                    raise ValueError('portable_forward_score_mismatch')
                child=pred[['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id',
                            'u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']].copy()
                child['score']=scores;child['scope']=scope;child['cutoff']=cutoff;child['arm']=arm
                child['member_q_raw']=q[plan['pi']];child['member_q_missing']=xp[:,52].astype(int);child['member_q_design']=xp[:,53]
                chosen,new_boundaries,selected_summary=choose_scope(parent,child,scope,arm,calendar)
                for epoch,value in new_boundaries.items():
                    if epoch in boundaries and boundaries[epoch] != value:
                        raise ValueError('inconsistent_shared_K_boundary')
                    boundaries[epoch]=value
                choices.append(chosen)
                seen=score_seen[(arm,scope=='main')]
                if seen[plan['pi']].any():
                    raise ValueError('duplicate_forward_child_score_identity')
                seen[plan['pi']]=True
                child.to_csv(output/'child_scores.csv.gz',index=False,float_format='%.17g',
                             mode='a',header=score_count==0,compression='gzip')
                score_count+=len(child)
                selection_summaries.append(dict(scope=scope,cutoff=cutoff,arm=arm,summary=selected_summary))
                records.append(dict(**report,arm=arm,dimension=54,training_identity_weights=train_b,
                    weight_groups=group_b,scaler=scaler_b,portable_model=portable_b,normal_equations=eq_b,
                    normal_equation_max_abs_residual=float(np.max(np.abs(eq['lhs']@eq['coefficient_with_intercept']-eq['rhs'])))))
                del xp,estimator
                print(json.dumps(dict(phase='fit_cell_completed',scope=scope,cutoff=cutoff,arm=arm,completed=completed)),flush=True)
        all_choices=pd.concat(choices,ignore_index=True)
        expected_parents=set(m.loc[m.u_date.ge(CUTOFFS[0]),'event_id'])
        expected_children=a.u_date.ge(CUTOFFS[0]).to_numpy()
        main=restore_parent_order(all_choices.loc[all_choices.scope.eq('main')].copy())
        held=restore_parent_order(all_choices.loc[all_choices.scope.ne('main')].copy())
        for arm in ARMS:
            for name,frame in [('main',main),('held_union',held)]:
                part=frame.loc[frame.arm.eq(arm)]
                if len(part)!=161014 or part.event_id.duplicated().any() or set(part.event_id)!=expected_parents:
                    raise ValueError('incomplete_forward_parent_domain '+name+' '+arm)
            for is_main in (True,False):
                seen=score_seen[(arm,is_main)]
                if int(seen.sum())!=966740 or not np.array_equal(seen,expected_children):
                    raise ValueError('incomplete_forward_child_domain '+arm)
        if attempts!=12 or completed!=12 or score_count!=3866960:
            raise ValueError('twelve_fit_full_forward_count_mismatch')
        if set(boundaries)!=set(a.loc[a.u_date.ge(CUTOFFS[0]),'reference_epoch']):
            raise ValueError('forward_epoch_boundary_domain_mismatch')
        diagnostic_choices=all_choices.copy();diagnostic_choices['arm']=diagnostic_choices.arm.map({ARMS[0]:'A',ARMS[1]:'B'})
        report,daily,_=old.held_diagnostics(diagnostic_choices,a)
        report.update(schema='stage167_original_target_held_diagnostic_v1',arm_aliases={'A':ARMS[0],'B':ARMS[1]},
                      contrast='CONCENTRATION54_minus_CONTROL54',target='original129 first-exit net_R_stress, not K-truncated return',
                      generalization_fully_qualified=False)
        for group in report['groups'].values():
            group['selected_by_arm']={ARMS[0]:group['selected_by_arm']['A'],ARMS[1]:group['selected_by_arm']['B']}
        role_bindings={}
        for role,frame in [('choices_main',main),('choices_holdout',held),('held_daily',daily)]:
            role_bindings[role]=save_csv(role+'.csv.gz',frame)
        role_bindings['child_scores']=file_binding(output/'child_scores.csv.gz')
        bindings['child_scores.csv.gz']=role_bindings['child_scores']
        role_bindings['held_diagnostic']=save_json('held_diagnostic.json',report)
        role_bindings['fit_records']=save_json('fit_records.json',records)
        role_bindings['boundaries']=save_json('boundaries.json',dict(schema='stage167_voluntary_epoch_boundaries_v1',
            protocol_sha256=PROTOCOL_SHA,policy_version=voluntary.POLICY_VERSION,not_certified=True,
            account_deadline_certified=False,calendar=auth['input_bindings']['calendar'],sample_end=END,epochs=boundaries))
        role_bindings['preflight']=preflight_b
        save_json('summary.json',dict(status='completed',actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,
            parent_rows_per_arm_main=161014,parent_rows_per_arm_held_union=161014,forward_child_scores=score_count,
            selection=selection_summaries,cumulative_fit=397+completed,cumulative_cash=210,goal_complete=False))
        if bundle!=source_bundle():
            raise ValueError('source_bundle_changed_during_fit')
        terminal=save_json('terminal.json',dict(status='completed',exit_code=0,actual_fit_calls_attempted=attempts,
            actual_fit_calls_completed=completed,actual_model_fit_calls=completed,elapsed_seconds=time.monotonic()-started,
            new_cash=0,new_SQL=0,downloads=0,automatic_retry=False))
        for name in ('fit_attempts.jsonl','fit_completed.jsonl'):
            bindings[name]=file_binding(output/name)
        save_json('manifest.json',dict(schema='stage167_member_concentration_fit_v1',status='completed',cash_eligible=True,
            actual_model_fit_calls=completed,actual_fit_calls_attempted=attempts,actual_fit_calls_completed=completed,
            protocol=protocol_binding,protocol_sha256=PROTOCOL_SHA,authorization=authorization,source_bundle=bundle,
            input_bindings=auth['input_bindings'],input_evidence=input_evidence,terminal=terminal,
            artifacts=dict(bindings),new_cash=0,new_SQL=0,downloads=0,production_qualified=False,goal_complete=False,**role_bindings))
    except BaseException as exc:
        if not (output/'terminal.json').exists():
            write_json(output/'terminal.json',dict(status='failed',exit_code=1,actual_fit_calls_attempted=attempts,
                actual_fit_calls_completed=completed,error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic()-started,automatic_retry=False,new_cash=0,new_SQL=0,downloads=0))
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','protocol-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+key,required=True)
    args=parser.parse_args(argv)
    output,auth,authorization,protocol_binding=authorize(args)
    run_actual(output,auth,authorization,protocol_binding)


if __name__=='__main__':
    main()
