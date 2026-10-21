"""Frozen453: six Ridge53 fits, complete original child IDs and same-K choices.

Import/fixtures do not read real data or fit estimators. Actual requires one
root authorization that accepts the independently reviewed six-fold source.
The original52 models/scores, targets, weights and scalers are never refitted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
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
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL = LINE/'outputs/stage453_Con4_fixed_protocol/protocol.json'
PROTOCOL_SHA = 'c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053'
CANDIDATE = 'COMMON52_PLUS_LAGGED_CON4_Z_RIDGE53'
SCOPES = ('main', 'holdout_0', 'holdout_1')
CUTOFFS = ('2020-01-01', '2023-01-01')
END = '2026-10-16'
PARAMETERS = dict(alpha=1., fit_intercept=True, solver='cholesky')
TRAIN_FIELDS = ['sequence_index', 'action_id', 'product_id', 'family_id', 'u_date', 'u_index',
                'reference_epoch', 'u_action_eligible', 'label_known_date', 'label_state',
                'net_R_stress', 'sample_weight', 'mother_sequence_index', 'mother_event_id']
SOURCE_NAMES = ('stage456_con4_fit_select.py', 'test_stage456_con4_fit_select.py',
                'stage130_contract_choice_fit.py', 'stage071_settlement_narrow_fit.py',
                'stage156_voluntary_choices.py', 'stage296_reopening_offset_fit_select.py',
                'stage285_wasde_offset_fit_select.py')
_MODULES = {}


def load(name):
    if name not in _MODULES:
        spec = importlib.util.spec_from_file_location('stage456_pure_'+name[:-3], TOOLS/name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULES[name] = module
    return _MODULES[name]


def original():
    return load('stage130_contract_choice_fit.py')


def selector():
    return load('stage156_voluntary_choices.py')


def cached():
    return load('stage296_reopening_offset_fit_select.py')


def binding(path):
    p = Path(path).resolve(); body = p.read_bytes()
    return dict(path=str(p), bytes=len(body), sha256=hashlib.sha256(body).hexdigest())


def same(a, b):
    return all(a.get(k) == b.get(k) for k in ('path', 'bytes', 'sha256'))


def read_bound(b):
    body = Path(b['path']).read_bytes()
    if len(body) != b['bytes'] or hashlib.sha256(body).hexdigest() != b['sha256']:
        raise ValueError('bound_input_changed '+b['path'])
    return body


def read_json(b):
    if b['bytes'] > 2*1024*1024:
        raise ValueError('metadata_size_limit')
    return json.loads(read_bound(b))


def inherited_stat(b):
    p = Path(b['path']); stat = p.stat()
    if not p.is_file() or stat.st_size != b['bytes']:
        raise ValueError('inherited_size_changed '+str(p))
    return dict(path=str(p.resolve()), bytes=stat.st_size, device=stat.st_dev,
                inode=stat.st_ino, mtime_ns=stat.st_mtime_ns, inherited_sha256=b['sha256'], rehashed=False)


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def source_bundle():
    return sorted((binding(TOOLS/n) for n in SOURCE_NAMES), key=lambda b: b['path'])


def require_source_support(source, review, auth):
    """This gate is called before any original target CSV or real array read."""
    cells = source.get('sixfold_source_support', [])
    keys = {(c.get('scope'), c.get('cutoff')) for c in cells}
    expected = {(s, c) for s in SCOPES for c in CUTOFFS}
    if (auth.get('source_support_accepted_by_root') is not True
            or source.get('status') != 'completed' or source.get('protocol_sha256') != PROTOCOL_SHA
            or source.get('all_support_passed') is not True or len(cells) != 6 or keys != expected
            or not all(c.get('passed') is True for c in cells)
            or review.get('status') != 'completed' or review.get('core_blockers') != 0
            or review.get('all_support_passed') is not True):
        raise ValueError('all_six_source_support_and_root_acceptance_required_before_Y')


def q_statistics(q, weights):
    q, w = np.asarray(q, float), np.asarray(weights, float)
    if q.ndim != 1 or q.shape != w.shape or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError('q_weight_identity')
    finite = np.isfinite(q)
    if np.isinf(q).any() or (np.abs(q[finite]) > 1).any():
        raise ValueError('Con4_outside_fixed_domain')
    mean = float(np.average(q[finite], weights=w[finite])) if finite.any() else None
    var = float(np.average((q[finite]-mean)**2, weights=w[finite])) if finite.any() else None
    ready = bool(mean is not None and np.isfinite(mean) and np.isfinite(var) and var > 0)
    return dict(ready=ready, mean=mean, var=var, scale=float(np.sqrt(var)) if ready else None,
                finite_count=int(finite.sum()), missing_count=int((~finite).sum()),
                finite_weight_sum=float(w[finite].sum()), missing_weight_sum=float(w[~finite].sum()))


def design53(common, q, scaler, stat):
    if not stat.get('ready'):
        raise ValueError('positive_original_train_Con4_variance_required')
    base = original().design(common, scaler)
    q = np.asarray(q, float)
    if q.shape != (len(base),) or np.isinf(q).any():
        raise ValueError('Con4_design_identity')
    finite = np.isfinite(q); z = np.zeros(len(q), dtype=float)
    z[finite] = (q[finite]-stat['mean'])/stat['scale']
    result = np.column_stack((base, z))
    if result.shape != (len(q), 53) or not np.isfinite(result).all():
        raise ValueError('finite_original52_plus_one_Con4_required')
    return result


def project_q(mother_q, indices):
    ii = np.asarray(indices)
    if (ii.ndim != 1 or ii.dtype.kind not in 'iu'
            or (ii < 0).any() or (ii >= len(mother_q)).any()):
        raise ValueError('action_mother_index_outside_fixed_domain')
    return np.asarray(mother_q)[ii]


def validate_training(frame, scope, cutoff, expected):
    train = cached().validate_training(frame, scope, cutoff, expected)
    for k in ('mother_sequence_index', 'mother_event_id'):
        train[k] = frame[k].to_numpy()
    a = train.mother_sequence_index.astype(float).to_numpy()
    if not np.isfinite(a).all() or not np.equal(a, np.floor(a)).all() or (a < 0).any():
        raise ValueError('training_parent_integer_identity')
    train['mother_sequence_index'] = a.astype(np.int64)
    return train


def ridge_system(x, y, w):
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    if (x.ndim != 2 or x.shape[1] != 53 or y.shape != (len(x),) or w.shape != y.shape
            or not all(np.isfinite(v).all() for v in (x, y, w)) or (w <= 0).any()):
        raise ValueError('ridge53_finite_equation_inputs')
    z = np.column_stack((x, np.ones(len(x))))
    lhs = z.T@(w[:, None]*z)
    lhs[np.arange(53), np.arange(53)] += 1.
    return lhs, z.T@(w*y)


def select_scope(mothers, scores, scope, calendar, end=END):
    if scope not in SCOPES:
        raise ValueError('unknown_fixed_scope')
    def aliases():
        for row in scores:
            if row['scope'] != scope:
                raise ValueError('mixed_forward_scope')
            yield dict(row, scope='main')
    result = selector().select_full_pool(mothers, aliases(), calendar, end, audit_sink=lambda row: None)
    for row in result['choices']:
        row.update(scope=scope, candidate=CANDIDATE)
    return result


def authorize(args):
    out = Path(args.output).resolve(); pb = binding(PROTOCOL)
    if pb['sha256'] != PROTOCOL_SHA:
        raise ValueError('frozen453_changed')
    if out.exists() or LINE/'outputs/stage456_Con4_fit_select' not in out.parents:
        raise ValueError('fresh_stage456_output_required')
    ab = binding(args.authorization)
    if ab['sha256'] != args.authorization_sha256:
        raise ValueError('authorization_changed')
    auth = read_json(ab)
    fixed = dict(schema='stage456_exact_root_authorization_v1', authorized_by='root',
                 exact_source_authorized=True, protocol_sha256=PROTOCOL_SHA, candidate=CANDIDATE,
                 output=str(out), max_new_fit=6, max_new_cash=0, source_support_accepted_by_root=True)
    if any(auth.get(k) != v for k, v in fixed.items()) or auth.get('source_bundle') != source_bundle():
        raise ValueError('exact456_root_authorization_required')
    p = read_json(pb); fixed_inputs = p['experiment_design452']['identity_reuse']['inputs']
    if auth.get('original_inputs') != fixed_inputs:
        raise ValueError('original453_input_bindings_required')
    return out, p, pb, auth, ab


def validate_inputs(p, auth):
    design = p['experiment_design452']; identity = design['identity_reuse']; inputs = auth['original_inputs']
    source = read_json(auth['source_manifest']); review = read_json(auth['source_review_receipt'])
    if source.get('schema') != 'stage454_con4_visible_source_manifest_v1':
        raise ValueError('completed454_source_schema_required')
    require_source_support(source, review, auth)
    if (not same(review.get('source_manifest', {}), auth['source_manifest'])
            or review.get('protocol_sha256') != PROTOCOL_SHA):
        raise ValueError('exact455_reviewed454_binding_required')
    if not same(source['inputs']['mothers'], inputs['mothers']):
        raise ValueError('source454_original_mothers')
    fit = read_json(inputs['fit_manifest'])
    if (not same(inputs['fit_manifest'], identity['original130_manifest']) or fit.get('status') != 'completed'
            or fit.get('actual_fit_calls_completed') != 6 or p['candidate'] != CANDIDATE
            or design['fit_contract']['parameters'] != PARAMETERS):
        raise ValueError('original130_or_fixed_Ridge_identity')
    for role in ('actions', 'mothers'):
        if not same(inputs[role], fit['input_bindings'][role]):
            raise ValueError('original129_'+role)
    if (not same(identity['original_common26'], fit['input_bindings']['common'])
            or not same(identity['old_control_scores'], fit['child_scores'])):
        raise ValueError('original_common_and_score_identity')
    cm = read_json(inputs['control_choice_manifest'])
    held = read_json(inputs['control_held_manifest']); heldreview = read_json(inputs['control_held_review'])
    if (not same(cm['artifacts']['choices_main'], inputs['control_choices_main']) or cm.get('parent_rows') != 161014
            or not same(held['control_held_K'], inputs['control_held_choices']) or held.get('control_arm') != 'COMMON52'
            or heldreview.get('status') != 'completed' or heldreview.get('core_blockers') != 0
            or not same(heldreview['manifest'], inputs['control_held_manifest'])):
        raise ValueError('accepted_same_K_common52_main_held_controls')
    records = read_json(fit['fit_records'])
    if len(records) != 6:
        raise ValueError('six_original_fit_records')
    cells = {(v['scope'], v['cutoff']): v for v in source['sixfold_source_support']}
    for f in identity['original130_folds']:
        r = next(v for v in records if (v['scope'], v['cutoff']) == (f['scope'], f['cutoff']))
        for k in ('training_rows', 'training_dates', 'training_families', 'training_groups',
                  'prediction_children', 'prediction_mothers', 'max_u_date', 'max_label_known_date'):
            if r[k] != f[k]:
                raise ValueError('original_fold_summary_'+k)
        for k in ('training_identity_weights', 'scaler', 'portable_model'):
            if not same(r[k], f[k]):
                raise ValueError('original_fold_binding_'+k)
        cell = cells[(f['scope'], f['cutoff'])]
        for k in ('training_identity_weights', 'scaler'):
            if not same(cell[k], f[k]):
                raise ValueError('source454_fold_binding_'+k)
    return design, inputs, source, cells


def validate_child_frame(chunk, mothers, scope_seen):
    for k in ('sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible'):
        v = chunk[k].astype(float).to_numpy()
        if not np.isfinite(v).all() or not np.equal(v, np.floor(v)).all() or (v < 0).any():
            raise ValueError('forward_integer_identity_'+k)
        chunk[k] = v.astype(np.int64)
    seq = chunk.sequence_index.to_numpy(); mi = chunk.mother_sequence_index.to_numpy()
    if ((seq >= 1552456).any() or (mi >= len(mothers)).any() or not chunk.u_action_eligible.isin([0, 1]).all()
            or not chunk.reference_epoch.str.rsplit('.', n=1).str[0].eq(chunk.product_id).all()):
        raise ValueError('forward_child_domain')
    for k in ('product_id', 'family_id', 'u_date', 'u_index'):
        if not np.array_equal(chunk[k].to_numpy(), mothers[k].to_numpy()[mi]):
            raise ValueError('forward_child_mother_'+k)
    if (not np.array_equal(chunk.mother_event_id.to_numpy(), mothers.event_id.to_numpy()[mi])
            or not np.array_equal(chunk.anchor_epoch.to_numpy(), mothers.reference_epoch.to_numpy()[mi])):
        raise ValueError('forward_parent_anchor_identity')
    expected = np.where(chunk.u_date.lt(CUTOFFS[1]), CUTOFFS[0], CUTOFFS[1])
    if not np.array_equal(chunk.cutoff.to_numpy(), expected) or chunk.u_date.lt(CUTOFFS[0]).any() or chunk.u_date.gt(END).any():
        raise ValueError('forward_cutoff_identity')
    for scope, part in chunk.groupby('scope', sort=False):
        if scope not in SCOPES:
            raise ValueError('unknown_forward_scope')
        if scope != 'main' and not part.family_id.map(original().family_group).eq(int(scope[-1])).all():
            raise ValueError('forward_held_family_scope')
        indices = part.sequence_index.to_numpy()
        if len(np.unique(indices)) != len(indices) or scope_seen[scope][indices].any():
            raise ValueError('duplicate_forward_child_sequence')
        scope_seen[scope][indices] = True
    return chunk


def predicted_rows(path, common, mother_q, episode_index, mothers, models, scalers, stats,
                   writer, counts, forecast):
    seen = {s: np.zeros(len(common), dtype=bool) for s in SCOPES}
    counts['score_csv_reads'] += 1
    for chunk in pd.read_csv(path, usecols=selector().SCORE_FIELDS, dtype=str, keep_default_na=False,
                             chunksize=100000, float_precision='round_trip'):
        chunk = validate_child_frame(chunk, mothers, seen)
        chunk['old_score'] = chunk.score.astype(float)
        if not np.isfinite(chunk.old_score).all():
            raise ValueError('original_forward_score_nonfinite')
        q = project_q(mother_q, chunk.mother_sequence_index.to_numpy())
        values = np.empty(len(chunk)); zs = np.zeros(len(chunk))
        for key, indices in chunk.groupby(['scope', 'cutoff'], sort=False).indices.items():
            if key not in models:
                raise ValueError('unknown_forward_fold')
            ii = np.asarray(indices, int); seq = chunk.iloc[ii].sequence_index.to_numpy()
            x = design53(common[seq], q[ii], scalers[key], stats[key])
            with threadpool_limits(limits=1):
                predicted = models[key].predict(x)
            portable = x@models[key].coef_+float(models[key].intercept_)
            if not np.allclose(predicted, portable, rtol=1e-12, atol=1e-12):
                raise ValueError('full_portable_Ridge53_prediction_mismatch')
            values[ii] = predicted; zs[ii] = x[:, 52]
            c = forecast.setdefault(key, Counter()); finite = np.isfinite(q[ii])
            delta = predicted-chunk.old_score.to_numpy()[ii]
            c['rows'] += len(ii); c['visible_q_rows'] += int(finite.sum()); c['NA_q_rows'] += int((~finite).sum())
            c['changed_scores'] += int(np.count_nonzero(delta)); c['NA_changed_scores'] += int(np.count_nonzero(delta[~finite]))
            c['negative_to_positive'] += int(np.count_nonzero((chunk.old_score.to_numpy()[ii] <= 0)&(predicted > 0)))
            c['positive_to_nonpositive'] += int(np.count_nonzero((chunk.old_score.to_numpy()[ii] > 0)&(predicted <= 0)))
            c['NA_max_abs_score_change'] = max(c.get('NA_max_abs_score_change', 0.), float(np.max(np.abs(delta[~finite]))) if (~finite).any() else 0.)
            counts['prediction_batches'] += 1
        if not np.isfinite(values).all():
            raise ValueError('new_forward_score_nonfinite')
        chunk['score'] = values; chunk['q_raw'] = q; chunk['q_z'] = zs
        chunk['source_episode_index'] = episode_index[chunk.mother_sequence_index.to_numpy()]
        counts['score_rows_read'] += len(chunk)
        for row in chunk.to_dict('records'):
            if not np.isfinite(row['q_raw']):
                row['q_raw'] = ''
            writer.writerow(row)
            yield row


def execute(args):
    out, p, pb, auth, ab = authorize(args)
    # Do not create a run or read any real target/array before accepted454+455.
    design, inputs, source, cells = validate_inputs(p, auth)
    out.mkdir(parents=True, exist_ok=False)
    began = time.monotonic(); bundle = source_bundle(); artifacts = {}; folds = []
    counts = Counter(dict(fit_attempted=0, fit_completed=0, cash=0, SQL=0, old52_refit=0,
                          old52_score_recalculation=0, new_labels=0, old_large_hash=0,
                          source_vector_reads=0, common_reads=0, mother_csv_reads=0,
                          training_csv_reads=0, score_csv_reads=0, score_rows_read=0,
                          prediction_batches=0, label_action_streams=0, control_choice_reads=0))
    status = 'failed'; error = None; changed_main = None; diagnostic = None
    def save_json(name, value):
        write_json(out/name, value); b = binding(out/name); artifacts[name.removesuffix('.json')] = b; return b
    def save_csv(name, frame):
        frame.to_csv(out/name, index=False, compression={'method': 'gzip', 'mtime': 0}, float_format='%.17g')
        b = binding(out/name); artifacts[name.removesuffix('.csv.gz')] = b; return b
    save_json('started.json', dict(protocol=pb, authorization=ab, source_bundle=bundle,
                                  source_support_accepted_before_Y=True, automatic_retry=False,
                                  versions=dict(sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__)))
    try:
        identity = design['identity_reuse']; original_folds = identity['original130_folds']
        large = {k: inputs[k] for k in ('mothers', 'actions', 'control_choices_main', 'control_held_choices')}
        large.update(common=identity['original_common26'], scores=identity['old_control_scores'])
        for f in original_folds:
            large[f['scope']+'/'+f['cutoff']] = f['training_identity_weights']
        before = {k: inherited_stat(b) for k, b in large.items()}
        calendar_array = np.load(io.BytesIO(read_bound(inputs['calendar'])), allow_pickle=False)
        calendar = ([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in calendar_array]
                    if calendar_array.dtype.kind in 'iu' else calendar_array.astype('datetime64[D]').astype(str).tolist())
        if len(calendar) != 5587 or calendar != sorted(set(calendar)):
            raise ValueError('original_calendar_identity')
        mothers = pd.read_csv(inputs['mothers']['path'], usecols=selector().IDENTITY, dtype=str, keep_default_na=False)
        counts['mother_csv_reads'] += 1
        for k in ('sequence_index', 'u_index'):
            mothers[k] = mothers[k].astype(np.int64)
        if (len(mothers) != 399252 or mothers.event_id.duplicated().any() or mothers.product_id.nunique() != 98
                or mothers.family_id.nunique() != 95 or not np.array_equal(mothers.sequence_index, np.arange(399252))
                or not np.array_equal(mothers.u_date, np.asarray(calendar)[mothers.u_index.to_numpy()])):
            raise ValueError('full_original_mothers_required')
        forward = mothers.loc[mothers.u_date.ge(CUTOFFS[0])&mothers.u_date.le(END)].reset_index(drop=True)
        if len(forward) != 161014:
            raise ValueError('full_forward_mothers_required')
        vector_binding = source['artifacts']['visible_mother_con4']
        with np.load(io.BytesIO(read_bound(vector_binding)), allow_pickle=False) as z:
            mother_q = z['q_raw']; sequence = z['sequence_index']; episodes = z['source_episode_index']
        counts['source_vector_reads'] += 1
        if (mother_q.shape != (399252,) or mother_q.dtype != np.dtype('float64') or np.isinf(mother_q).any()
                or sequence.dtype.kind not in 'iu' or not np.array_equal(sequence, np.arange(399252))
                or episodes.shape != mother_q.shape or episodes.dtype.kind not in 'iu'
                or (episodes < -1).any() or (episodes >= 6680).any()
                or not np.array_equal(np.isfinite(mother_q), episodes >= 0)
                or (np.abs(mother_q[np.isfinite(mother_q)]) > 1).any()
                or not mothers.loc[np.isfinite(mother_q), 'product_id'].isin(design['column_contract']['fixed_mapping']).all()):
            raise ValueError('accepted454_vector_shape_identity_missing_or_mapping')
        with np.load(identity['original_common26']['path'], allow_pickle=False) as z:
            common = z['common']; columns = z['columns'].tolist()
        counts['common_reads'] += 1
        if common.shape != (1552456, 26) or columns != original().COMMON:
            raise ValueError('unchanged_original_common26_required')
        models = {}; scalers = {}; statistics = {}
        for f in original_folds:
            scope, cutoff = f['scope'], f['cutoff']; key = (scope, cutoff)
            scaler = read_json(f['scaler'])
            if (scaler['feature_names'] != original().FEATURE_NAMES or scaler['common']['columns'] != columns
                    or scaler['scope'] != scope or scaler['cutoff'] != cutoff):
                raise ValueError('original_fold_common52_scaler')
            # First and only training CSV read: all six source gates already passed above.
            frame = pd.read_csv(f['training_identity_weights']['path'], usecols=TRAIN_FIELDS, dtype=str,
                                keep_default_na=False, float_precision='round_trip')
            counts['training_csv_reads'] += 1
            train = validate_training(frame, scope, cutoff, f['training_rows'])
            ti = train.sequence_index.to_numpy(); mi = train.mother_sequence_index.to_numpy()
            if ((ti >= len(common)).any() or (mi >= len(mothers)).any()
                    or train.u_date.nunique() != f['training_dates'] or train.family_id.nunique() != f['training_families']
                    or train.u_date.max() != f['max_u_date'] or train.label_known_date.max() != f['max_label_known_date']):
                raise ValueError('original_training_summary')
            for k in ('product_id', 'family_id', 'u_date', 'u_index'):
                if not np.array_equal(train[k].to_numpy(), mothers[k].to_numpy()[mi]):
                    raise ValueError('training_parent_identity_'+k)
            if not np.array_equal(train.mother_event_id.to_numpy(), mothers.event_id.to_numpy()[mi]):
                raise ValueError('training_parent_event_identity')
            q = project_q(mother_q, mi); w = train.sample_weight.to_numpy(); y = train.net_R_stress.to_numpy()
            stat = q_statistics(q, w); accepted_stat = cells[key]['q_statistics']
            if not stat['ready'] or not accepted_stat['ready']:
                raise ValueError('accepted_source_variance_lost')
            for k in ('mean', 'var', 'scale', 'finite_count', 'finite_weight_sum'):
                if not np.isclose(stat[k], accepted_stat[k], rtol=1e-13, atol=1e-14):
                    raise ValueError('accepted_source_fold_stat_'+k)
            x = design53(common[ti], q, scaler, stat); model = Ridge(**PARAMETERS)
            counts['fit_attempted'] += 1
            save_json('fit_attempt_'+str(counts['fit_attempted'])+'.json', dict(scope=scope, cutoff=cutoff, **dict(counts)))
            with threadpool_limits(limits=1):
                model.fit(x, y, sample_weight=w)
            counts['fit_completed'] += 1
            with threadpool_limits(limits=1):
                lhs, rhs = ridge_system(x, y, w)
            beta = np.r_[model.coef_, model.intercept_]
            if not np.isfinite(beta).all() or not np.allclose(lhs@beta, rhs, rtol=1e-8, atol=1e-7):
                raise ValueError('Ridge53_normal_equation_mismatch')
            stem = scope+'_'+cutoff
            equation_path = out/('normal_equations_'+stem+'.npz')
            with equation_path.open('xb') as stream:
                np.savez_compressed(stream, lhs=lhs, rhs=rhs, coefficient_with_intercept=beta, weight_sum=np.array(w.sum()))
            eb = binding(equation_path); artifacts['normal_equations_'+stem] = eb
            feature_names = original().FEATURE_NAMES+['Con4Net_All_visible_train_weighted_z']
            portable = dict(schema='stage456_portable_Ridge53_v1', candidate=CANDIDATE, scope=scope,
                            cutoff=cutoff, parameters=PARAMETERS, feature_names=feature_names,
                            coef=model.coef_.tolist(), intercept=float(model.intercept_),
                            original_common_scaler=f['scaler'], Con4_statistics=stat,
                            training_identity_weights=f['training_identity_weights'], base52_capacity_scale=1., Con4_capacity_scale=1.)
            mb = save_json('portable_'+stem+'.json', portable)
            sb = save_json('scaler_'+stem+'.json', dict(original_common_scaler=f['scaler'], Con4_statistics=stat,
                          feature_names=feature_names, scope=scope, cutoff=cutoff, no_new_missing_flag=True))
            modelpath = out/('model_'+stem+'.joblib')
            with modelpath.open('xb') as stream:
                joblib.dump(model, stream, compress=3)
            jb = binding(modelpath); artifacts['model_'+stem] = jb
            record = dict(scope=scope, cutoff=cutoff, training_rows=len(train), training_dates=f['training_dates'],
                          training_families=f['training_families'], training_groups=f['training_groups'],
                          max_u_date=f['max_u_date'], max_label_known_date=f['max_label_known_date'],
                          training_identity_weights=f['training_identity_weights'], original_scaler=f['scaler'],
                          scaler=sb, model=jb, portable_model=mb, normal_equations=eb,
                          dimension=53, parameters=PARAMETERS, sample_weight_sum=float(w.sum()),
                          q_statistics=stat, training_weights_renormalized=False,
                          normal_equation_max_abs_residual=float(np.max(np.abs(lhs@beta-rhs))),
                          prediction_children=f['prediction_children'], prediction_mothers=f['prediction_mothers'])
            folds.append(record); save_json('fold_'+stem+'.json', record)
            models[key] = model; scalers[key] = scaler; statistics[key] = stat
            del x, frame, train
            print(json.dumps(dict(phase='Con4_Ridge53_fold_complete', scope=scope, cutoff=cutoff, completed=counts['fit_completed'])), flush=True)
        if counts['fit_attempted'] != 6 or counts['fit_completed'] != 6:
            raise ValueError('exact_six_new_fits_required')
        choices = []; boundaries = {}; summaries = []; forecast = {}; seen_scopes = []
        scorepath = out/'child_scores.csv.gz'
        with gzip.open(scorepath, 'xt', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=selector().SCORE_FIELDS+['old_score', 'q_raw', 'q_z', 'source_episode_index'])
            writer.writeheader()
            rows = predicted_rows(identity['old_control_scores']['path'], common, mother_q, episodes, mothers,
                                  models, scalers, statistics, writer, counts, forecast)
            for scope, part in itertools.groupby(rows, key=lambda row: row['scope']):
                if scope not in SCOPES or scope in seen_scopes:
                    raise ValueError('noncontiguous_forward_scope')
                seen_scopes.append(scope)
                parents = forward if scope == 'main' else forward.loc[forward.family_id.map(original().family_group).eq(int(scope[-1]))]
                result = select_scope(parents.to_dict('records'), part, scope, calendar)
                choices.append(pd.DataFrame(result['choices'])); summaries.append(dict(scope=scope, **result['summary']))
                for epoch, b in result['boundaries'].items():
                    if epoch in boundaries and boundaries[epoch] != b:
                        raise ValueError('same_K_boundary_changed')
                    boundaries[epoch] = b
        artifacts['child_scores'] = binding(scorepath)
        if seen_scopes != list(SCOPES) or counts['score_rows_read'] != 1933480:
            raise ValueError('complete_original_child_score_domain')
        for f in original_folds:
            if forecast.get((f['scope'], f['cutoff']), {}).get('rows') != f['prediction_children']:
                raise ValueError('complete_original_fold_children')
        combined = pd.concat(choices, ignore_index=True)
        main = combined.loc[combined.scope.eq('main')].sort_values('sequence_index').reset_index(drop=True)
        held = combined.loc[combined.scope.ne('main')].sort_values('sequence_index').reset_index(drop=True)
        for frame in (main, held):
            if len(frame) != 161014 or frame.event_id.tolist() != forward.event_id.tolist():
                raise ValueError('full_main_and_held_union_parent_identity')
        control = cached().read_choices(inputs['control_choices_main'], forward)
        oldheld = cached().read_choices(inputs['control_held_choices'], forward, True)
        counts['control_choice_reads'] += 2
        changed_main = int(np.count_nonzero(main.chosen_action_id.to_numpy() != control.chosen_action_id.to_numpy()))
        changed_held = int(np.count_nonzero(held.chosen_action_id.to_numpy() != oldheld.chosen_action_id.to_numpy()))
        if changed_held:
            ids = set(oldheld.loc[oldheld.selected.eq(1), 'chosen_action_id']) | set(held.loc[held.selected.eq(1), 'chosen_action_id'])
            labels = cached().label_subset(inputs['actions']['path'], ids, counts)
        else:
            labels = pd.DataFrame(columns=cached().LABEL_FIELDS); labels['net_R_stress'] = pd.Series(dtype=float)
        diagnostic, daily = cached().held_diagnostic(oldheld, held, labels, labels_skipped=not changed_held)
        diagnostic.update(schema='stage456_Con4_held_original_target_v1', candidate=CANDIDATE,
                          target='original129 first-exit net_R_stress; not K cash', not_cash_admission_veto=True)
        save_csv('choices_main.csv.gz', main)
        save_csv('choices_held.csv.gz', held); artifacts['choices_holdout'] = artifacts['choices_held']
        save_json('boundaries.json', dict(schema='stage156_voluntary_K_only_v1', epochs=boundaries,
                  policy_version=selector().POLICY_VERSION, sample_end=END, calendar=inputs['calendar'], account_deadline_certified=False))
        save_json('held_diagnostic.json', diagnostic); save_csv('held_daily.csv.gz', daily)
        save_json('selection_summary.json', dict(scopes=summaries, changed_main_parent_choices=changed_main,
                  changed_held_parent_choices=changed_held, cash_eligible=bool(changed_main), same_K_controls=True,
                  held_diagnostic_is_cash_veto=False))
        save_json('forward_summary.json', dict(folds=[dict(scope=k[0], cutoff=k[1], **dict(v)) for k, v in forecast.items()],
                  full_score_identities_preserved=True, source_score_rows=1933480,
                  NA_direct_Con4_contribution=0., NA_scores_may_change_due_to_refit52=True))
        after = {k: inherited_stat(b) for k, b in large.items()}
        if before != after or source_bundle() != bundle:
            raise ValueError('accepted_old_inputs_or_source_changed_during_actual')
        save_json('source_read_receipt.json', dict(before=before, after=after, **dict(counts)))
        save_json('fit_records.json', folds)
        status = 'completed'
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)
        raise
    finally:
        terminal = save_json('actual_terminal.json', dict(status=status, exit_code=0 if status == 'completed' else 1,
                  elapsed_seconds=time.monotonic()-began, error=error, automatic_retry=False,
                  counters=dict(counts), new_cash_accounts=0, production_qualified=False))
        manifest = dict(schema='stage456_con4_fit_select_manifest_v1', status=status, candidate=CANDIDATE,
                  protocol=pb, protocol_sha256=PROTOCOL_SHA, authorization=ab, source_bundle=bundle,
                  source_manifest=auth['source_manifest'], source_review_receipt=auth['source_review_receipt'],
                  inputs=inputs, input_bindings=inputs, identity_inputs=design['identity_reuse'],
                  artifacts=artifacts, folds=folds, fit_records=artifacts.get('fit_records'), terminal=terminal,
                  changed_main_parent_choices=changed_main, cash_eligible=bool(changed_main) and status == 'completed',
                  held_diagnostic=artifacts.get('held_diagnostic'), counters=dict(counts),
                  new_model_fit_calls=counts['fit_completed'], new_cash_accounts=0,
                  old52_refit=0, old52_score_recalculation=0, held_diagnostic_is_cash_veto=False,
                  increased_betting_qualified=False, production_qualified=False, goal_complete=False)
        write_json(out/'manifest.json', manifest)
    return dict(status=status, output=str(out), new_model_fit_calls=counts['fit_completed'], new_cash_accounts=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--output', required=True)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
