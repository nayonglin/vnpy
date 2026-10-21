"""Frozen469 annual mature COMMON52 update; import/fixtures read no real data.

One original actions usecols stream serves fitting, held diagnostics and the
cash handoff. Original2020/2023 same-year scores/models are reused, never fitted
or predicted anew. Cash deployment folds remain2020/2023 across annual updates.
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
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
OUTPUT_ROOT = LINE/'outputs/stage470_annual_mature_fit_select'
PROTOCOL = LINE/'outputs/stage469_annual_mature_update_protocol/protocol.json'
PROTOCOL_SHA = 'f62281e099200e065785b61cc89a47a2111fe7d3dbf2ec60102b167b0708d4f6'
CANDIDATE = 'C_RESEARCH_COMMON52_FIXED_ANNUAL_MATURE_UPDATE'
SCOPES = ('main', 'holdout_0', 'holdout_1')
YEARS = tuple(range(2020, 2027))
REUSE_YEARS = (2020, 2023)
END = '2026-10-16'
PARAMETERS = dict(alpha=1., fit_intercept=True, solver='cholesky')
CASH_FIELDS = ['action_id', 'event_id', 'action_sequence_index', 'mother_sequence_index',
    'mother_event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch',
    'anchor_epoch', 'u_action_eligible', 'entry_capacity_qty', 'N_u', 'low20_u', 'u_close']
SOURCE_NAMES = ('stage470_annual_mature_fit_select.py', 'test_stage470_annual_mature_fit_select.py',
    'stage130_contract_choice_fit.py', 'stage071_settlement_narrow_fit.py', 'stage156_voluntary_choices.py')
_MODULES = {}


def load(name):
    if name not in _MODULES:
        spec = importlib.util.spec_from_file_location('stage470_pure_'+name[:-3], TOOLS/name)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        _MODULES[name] = module
    return _MODULES[name]


def original():
    return load('stage130_contract_choice_fit.py')


def selector():
    return load('stage156_voluntary_choices.py')


def binding(path):
    p = Path(path).resolve(); h = hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return dict(path=str(p), bytes=p.stat().st_size, sha256=h.hexdigest())


def same(left, right):
    return all(left.get(k) == right.get(k) for k in ('path', 'bytes', 'sha256'))


def read_bound(bound):
    raw = Path(bound['path']).read_bytes()
    if len(raw) != bound['bytes'] or hashlib.sha256(raw).hexdigest() != bound['sha256']:
        raise ValueError('bound_input_changed '+bound['path'])
    return raw


def read_json(bound):
    if bound['bytes'] > 2*1024*1024:
        raise ValueError('metadata_size_limit')
    return json.loads(read_bound(bound))


def inherited_stat(bound):
    p = Path(bound['path']).resolve(); s = p.stat()
    if not p.is_file() or s.st_size != bound['bytes']:
        raise ValueError('inherited_size_changed '+str(p))
    return dict(path=str(p), bytes=s.st_size, device=s.st_dev, inode=s.st_ino,
                mtime_ns=s.st_mtime_ns, inherited_sha256=bound['sha256'], rehashed=False)


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush()
    return binding(path)


def source_bundle():
    return sorted((binding(TOOLS/n) for n in SOURCE_NAMES), key=lambda b: b['path'])


def annual_cutoff(day):
    if len(day) != 10 or day[:4] not in {str(y) for y in YEARS}:
        raise ValueError('outside_fixed_annual_prediction_year')
    return day[:4]+'-01-01'


def annual_plan():
    return [dict(scope=s, training_cutoff=f'{y}-01-01', next_cutoff=f'{y+1}-01-01',
                 reused=y in REUSE_YEARS) for s in SCOPES for y in YEARS]


def dispatch_cell(cell, fit_new, reuse_old):
    """One fixed dispatch, also checked without estimator fits by the fixture."""
    return reuse_old(cell) if cell['reused'] else fit_new(cell)


def fold_slices(actions, mothers, cell):
    train, pred, parent = original().fold_slices(actions, mothers, cell['training_cutoff'],
                                               cell['next_cutoff'], cell['scope'])
    pred = pred.loc[pred.u_date.le(END)].copy()
    parent = parent.loc[parent.u_date.le(END)].copy()
    if pred.empty or parent.empty:
        raise ValueError('empty_fixed_annual_prediction_domain')
    return train, pred, parent


def select_scope(mothers, rows, scope, calendar, audit_sink=None):
    if scope not in SCOPES:
        raise ValueError('unknown_annual_scope')
    def aliases():
        for row in rows:
            if row['scope'] != scope or row['training_cutoff'] != annual_cutoff(row['u_date']):
                raise ValueError('annual_prediction_scope_or_clock')
            if row['cutoff'] != selector().cutoff_for(row['u_date']):
                raise ValueError('deployment_fold_must_not_be_annual')
            yield dict(row, scope='main')
    result = selector().select_full_pool(mothers, aliases(), calendar, END,
                                        audit_sink=audit_sink or (lambda row: None))
    for row in result['choices']:
        row.update(scope=scope, candidate=CANDIDATE, training_cutoff=annual_cutoff(row['u_date']),
                   deployment_fold_cutoff=row['cutoff'])
    return result


def action_columns():
    return list(dict.fromkeys(original().ACTION_COLUMNS+CASH_FIELDS))


def read_actions_once(bound, mothers, counts):
    """The only original129 action CSV stream in fit+cash, with union usecols."""
    numeric = list(dict.fromkeys(original().NUMERIC+['N_u', 'low20_u', 'u_close']))
    parts = []
    counts['original_action_streams'] += 1
    for chunk in pd.read_csv(bound['path'], usecols=action_columns(), dtype=str,
            keep_default_na=False, float_precision='round_trip', chunksize=100000):
        for key in numeric:
            chunk[key] = pd.to_numeric(chunk[key], errors='coerce')
        parts.append(chunk)
    a = pd.concat(parts, ignore_index=True); del parts
    if (len(a) != 1552456 or a.action_id.duplicated().any()
            or not np.array_equal(a.sequence_index, np.arange(len(a)))
            or not a.sequence_index.eq(a.action_sequence_index).all()
            or not a.event_id.eq(a.action_id).all() or not a.actual_epoch.eq(a.reference_epoch).all()
            or not a.u_action_eligible.isin([0, 1]).all()):
        raise ValueError('full_original_action_alias_identity')
    for key in ('sequence_index', 'action_sequence_index', 'mother_sequence_index', 'u_index'):
        values = a[key].to_numpy()
        if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
            raise ValueError('integer_original_action_'+key)
        a[key] = values.astype(np.int64)
    mi = a.mother_sequence_index.to_numpy()
    if (mi < 0).any() or (mi >= len(mothers)).any():
        raise ValueError('original_action_parent_domain')
    for key in ('product_id', 'family_id', 'u_date', 'u_index'):
        if not np.array_equal(a[key].to_numpy(), mothers[key].to_numpy()[mi]):
            raise ValueError('original_action_parent_'+key)
    if (not np.array_equal(a.mother_event_id, mothers.event_id.to_numpy()[mi])
            or not np.array_equal(a.anchor_epoch, mothers.reference_epoch.to_numpy()[mi])):
        raise ValueError('original_action_parent_event_or_anchor')
    counts['original_action_rows'] = len(a)
    return a


def reuse_scores_once(bound, actions, counts):
    """Scan the old file once, retaining only exact annual2020/2023 slices."""
    result = {s: np.full(len(actions), np.nan) for s in SCOPES}
    seen = {s: np.zeros(len(actions), dtype=bool) for s in SCOPES}
    counts['original_score_streams'] += 1
    for c in pd.read_csv(bound['path'], usecols=selector().SCORE_FIELDS, dtype=str,
            keep_default_na=False, float_precision='round_trip', chunksize=100000):
        counts['original_score_rows'] += len(c)
        for key in ('sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible'):
            c[key] = pd.to_numeric(c[key], errors='raise').astype(np.int64)
        seq = c.sequence_index.to_numpy()
        if (seq < 0).any() or (seq >= len(actions)).any():
            raise ValueError('original_score_sequence_domain')
        for key in ('action_id', 'mother_sequence_index', 'mother_event_id', 'product_id',
                    'family_id', 'u_date', 'u_index', 'reference_epoch', 'anchor_epoch', 'u_action_eligible'):
            if not np.array_equal(c[key].to_numpy(), actions[key].to_numpy()[seq]):
                raise ValueError('original_score_action_identity_'+key)
        expected_cutoff = np.where(c.u_date.lt('2023-01-01'), '2020-01-01', '2023-01-01')
        if (not np.array_equal(c.cutoff.to_numpy(), expected_cutoff)
                or c.u_date.lt('2020-01-01').any() or c.u_date.gt(END).any()):
            raise ValueError('original_score_deployment_fold')
        values = c.score.astype(float).to_numpy()
        if not np.isfinite(values).all():
            raise ValueError('original_score_nonfinite')
        for scope, ix in c.groupby('scope', sort=False).indices.items():
            if scope not in SCOPES:
                raise ValueError('original_score_unknown_scope')
            ii = np.asarray(ix); ss = seq[ii]
            if len(np.unique(ss)) != len(ss) or seen[scope][ss].any():
                raise ValueError('original_score_duplicate')
            if scope != 'main' and not c.iloc[ii].family_id.map(original().family_group).eq(int(scope[-1])).all():
                raise ValueError('original_score_held_scope')
            seen[scope][ss] = True
            keep = c.iloc[ii].u_date.str[:4].isin([str(y) for y in REUSE_YEARS]).to_numpy()
            result[scope][ss[keep]] = values[ii[keep]]
    forward = actions.u_date.ge('2020-01-01') & actions.u_date.le(END)
    for scope in SCOPES:
        domain = forward if scope == 'main' else forward & actions.family_id.map(original().family_group).eq(int(scope[-1]))
        if not np.array_equal(seen[scope], domain.to_numpy()):
            raise ValueError('full_original_score_domain_'+scope)
    if counts['original_score_rows'] != 1933480:
        raise ValueError('full_original_score_rows')
    return result


def fit_new_cell(actions, mothers, common, cell, out, counts):
    old = original(); train, pred, parents = fold_slices(actions, mothers, cell)
    scope, cutoff = cell['scope'], cell['training_cutoff']
    ti = train.sequence_index.to_numpy(); pi = pred.sequence_index.to_numpy()
    weights_frame, groups = old.training_weights(train)
    weights = weights_frame.sample_weight.to_numpy(float); y = train.net_R_stress.to_numpy(float)
    stats = [old.legacy.finite_stats(common[ti, j], weights) for j in range(26)]
    scaler = dict(common=dict(columns=old.COMMON, **{k: [s[k] for s in stats]
        for k in ('mean', 'var', 'scale', 'finite_count')}), feature_names=old.FEATURE_NAMES,
        scope=scope, cutoff=cutoff, weighting='family_u_interval_union_then_divide_actions_then_equal_u',
        missing='raw nonfinite standardized0 plus missing flag', units='COMMON unchanged original2N')
    directory = out/'folds'/scope/cutoff; directory.mkdir(parents=True, exist_ok=False)
    scaler_b = write_json(directory/'scaler.json', scaler)
    # Preserve every training member and all exact numeric weights, but no cash-only columns.
    train_out = train[old.ACTION_COLUMNS].copy().reset_index(drop=True)
    for key in weights_frame:
        train_out[key] = weights_frame[key].to_numpy()
    training_b = old.write_csv(directory/'training_identity_weights.csv.gz', train_out)
    groups_b = old.write_csv(directory/'weight_groups.csv.gz', groups)
    del train_out
    x = old.design(common[ti], scaler); model = old.legacy.Ridge(**PARAMETERS)
    counts['fit_attempted'] += 1
    write_json(directory/'fit_attempt.json', dict(cell=cell, fit_attempted=counts['fit_attempted'],
        training_rows=len(train), training_identity_weights=training_b, scaler=scaler_b))
    with old.legacy.threadpool_limits(limits=1):
        model.fit(x, y, sample_weight=weights)
    counts['fit_completed'] += 1
    with old.legacy.threadpool_limits(limits=1):
        z = np.column_stack([x, np.ones(len(x))]); lhs = z.T@(weights[:, None]*z)
        lhs[np.arange(52), np.arange(52)] += 1.; rhs = z.T@(weights*y)
    beta = np.r_[model.coef_, model.intercept_]; residual = lhs@beta-rhs
    if not np.isfinite(beta).all() or not np.allclose(lhs@beta, rhs, rtol=1e-8, atol=1e-7):
        raise ValueError('annual_original52_normal_equation_mismatch')
    equations_b = old.write_npz(directory/'normal_equations.npz', lhs=lhs, rhs=rhs,
        coefficient_with_intercept=beta, weight_sum=np.array(weights.sum()))
    portable = dict(schema='stage470_annual_portable_ridge52_v1', candidate=CANDIDATE,
        scope=scope, cutoff=cutoff, training_cutoff=cutoff, parameters=PARAMETERS,
        feature_names=old.FEATURE_NAMES, coef=model.coef_.tolist(), intercept=float(model.intercept_))
    portable_b = write_json(directory/'portable_model.json', portable)
    with (directory/'model.joblib').open('xb') as stream:
        old.legacy.joblib.dump(model, stream, compress=3)
    del x, z
    xp = old.design(common[pi], scaler)
    with old.legacy.threadpool_limits(limits=1):
        scores = model.predict(xp)
    if not np.allclose(scores, xp@np.array(portable['coef'])+portable['intercept'], rtol=1e-12, atol=1e-12):
        raise ValueError('annual_portable_scores')
    prediction_b = old.write_npz(directory/'prediction_checkpoint.npz', sequence_index=pi, score=scores)
    record = dict(scope=scope, cutoff=cutoff, training_cutoff=cutoff, reused=False,
        training_rows=len(train), training_dates=int(train.u_date.nunique()),
        training_families=int(train.family_id.nunique()), training_groups=len(groups),
        prediction_children=len(pred), prediction_mothers=len(parents), max_u_date=str(train.u_date.max()),
        max_label_known_date=str(train.label_known_date.max()), dimension=52, parameters=PARAMETERS,
        training_identity_weights=training_b, weight_groups=groups_b, scaler=scaler_b,
        portable_model=portable_b, model=binding(directory/'model.joblib'), normal_equations=equations_b,
        normal_equation_max_abs_residual=float(np.max(np.abs(residual))), prediction_checkpoint=prediction_b)
    write_json(directory/'completed.json', record)
    print(json.dumps(dict(phase='annual_fit_complete', scope=scope, training_cutoff=cutoff,
                         fit_completed=counts['fit_completed'])), flush=True)
    return pi, scores, record


def read_control(bound, mothers, held=False):
    fields = selector().IDENTITY+['selected', 'chosen_action_id', 'chosen_epoch',
                                 'chosen_action_sequence_index', 'scope']
    c = pd.read_csv(bound['path'], usecols=fields, dtype=str, keep_default_na=False)
    for key in ('sequence_index', 'u_index', 'selected', 'chosen_action_sequence_index'):
        c[key] = c[key].astype(np.int64)
    c = c.sort_values('sequence_index', kind='stable').reset_index(drop=True)
    for key in selector().IDENTITY:
        if c[key].tolist() != mothers[key].tolist():
            raise ValueError('accepted_control_parent_'+key)
    expected = mothers.family_id.map(original().family_group).map(lambda g: 'holdout_'+str(g)) if held else pd.Series('main', index=mothers.index)
    if c.scope.tolist() != expected.tolist() or not c.selected.isin([0, 1]).all():
        raise ValueError('accepted_control_scope')
    return c


def authorize(args):
    out = Path(args.output).resolve(); pb = binding(PROTOCOL)
    if pb['sha256'] != PROTOCOL_SHA:
        raise ValueError('frozen469_changed')
    if out.exists() or OUTPUT_ROOT not in out.parents:
        raise ValueError('fresh_stage470_output_required')
    ab = binding(args.authorization)
    if ab['sha256'] != args.authorization_sha256:
        raise ValueError('authorization_sha256')
    auth = read_json(ab)
    expected = dict(schema='stage470_exact_root_authorization_v1', authorized_by='root',
        exact_source_authorized=True, protocol_sha256=PROTOCOL_SHA, candidate=CANDIDATE,
        output=str(out), max_new_fit=15, max_new_cash=0)
    if any(auth.get(k) != v for k, v in expected.items()) or auth.get('source_bundle') != source_bundle():
        raise ValueError('exact470_root_authorization_required')
    fixture = read_json(auth['fixture_terminal'])
    if (fixture.get('status') != 'completed' or fixture.get('failures') != 0
            or fixture.get('actual_model_fit_calls') != 0 or fixture.get('source_bundle') != source_bundle()):
        raise ValueError('exact470_zero_model_fixture_required')
    return out, read_json(pb), pb, auth, ab


def execute(args):
    out, p, pb, auth, ab = authorize(args)
    if (p['candidate']['name'] != CANDIDATE or p['candidate']['cutoffs'] != [f'{y}-01-01' for y in YEARS]
            or p['candidate']['scopes'] != list(SCOPES)
            or p['candidate']['model_parameters'] != dict(PARAMETERS, features=52)):
        raise ValueError('frozen_annual_design_identity')
    inputs = p['input_bindings']; cash_contract = p['cash_contract_inherited_exact']
    source453 = read_json(inputs['source453_cash_contract'])
    control_inputs = source453['experiment_design452']['identity_reuse']['inputs']
    oldmanifest = read_json(p['control']['model_manifest'])
    records = read_json(inputs['original130_fit_records'])
    if (oldmanifest.get('status') != 'completed' or oldmanifest.get('actual_fit_calls_completed') != 6
            or len(records) != 6 or not same(oldmanifest['child_scores'], inputs['original130_scores'])):
        raise ValueError('completed_original_six_fits_required')
    for role, original_role in [('actions', 'original_actions'), ('mothers', 'original_mothers'), ('common', 'original_common')]:
        if not same(oldmanifest['input_bindings'][role], inputs[original_role]):
            raise ValueError('original130_dataset_'+role)
    reused = {(r['scope'], r['training_cutoff']): r for r in p['candidate']['reused_six_fits']}
    for r in records:
        rr = reused[(r['scope'], r['cutoff'])]
        if not same(r['portable_model'], rr['model']) or not same(r['scaler'], rr['scaler']):
            raise ValueError('frozen_reused_model_scaler_binding')
        read_json(rr['model']); read_json(rr['scaler'])
    out.mkdir(parents=True, exist_ok=False); started = time.monotonic(); bundle = source_bundle()
    artifacts = {}; folds = []; status = 'failed'; error = None; changed_main = changed_held = None
    counts = Counter(dict(fit_attempted=0, fit_completed=0, reused_fits=0, cash=0, SQL=0,
        API=0, download=0, original_action_streams=0, original_action_rows=0, common_reads=0,
        original_score_streams=0, original_score_rows=0, mother_streams=0, control_choice_reads=0,
        output_child_rows=0, old_large_hash=0, old_control_refits=0, old_control_score_recalculations=0))
    def save_json(name, value):
        b = write_json(out/name, value); artifacts[name.removesuffix('.json')] = b; return b
    def save_csv(name, frame):
        b = original().write_csv(out/name, frame); artifacts[name.removesuffix('.csv.gz')] = b; return b
    save_json('started.json', dict(schema='stage470_started_v1', protocol=pb, authorization=ab,
        source_bundle=bundle, automatic_retry=False, fixture_terminal=auth['fixture_terminal'],
        versions=dict(numpy=np.__version__, pandas=pd.__version__, sklearn=original().legacy.sklearn.__version__)))
    large = {k: inputs[k] for k in ('original_actions', 'original_mothers', 'original_common', 'original130_scores')}
    large.update(control_choices_main=control_inputs['control_choices_main'], control_held_choices=control_inputs['control_held_choices'])
    before = {k: inherited_stat(v) for k, v in large.items()}
    try:
        calendar_b = cash_contract['market_dependencies_inherited']['calendar']
        raw_calendar = read_bound(calendar_b)
        with (out/'calendar.npy').open('xb') as stream:
            stream.write(raw_calendar)
        artifacts['calendar'] = binding(out/'calendar.npy')
        cal = np.load(io.BytesIO(raw_calendar), allow_pickle=False)
        calendar = ([f'{int(v):08d}'[:4]+'-'+f'{int(v):08d}'[4:6]+'-'+f'{int(v):08d}'[6:] for v in cal]
                    if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist())
        if len(calendar) != 5587 or calendar != sorted(set(calendar)):
            raise ValueError('original_full_calendar')
        mothers = pd.read_csv(inputs['original_mothers']['path'], usecols=selector().IDENTITY,
                              dtype=str, keep_default_na=False)
        counts['mother_streams'] += 1
        for key in ('sequence_index', 'u_index'):
            mothers[key] = mothers[key].astype(np.int64)
        if (len(mothers) != 399252 or mothers.product_id.nunique() != 98 or mothers.family_id.nunique() != 95
                or mothers.event_id.duplicated().any() or not np.array_equal(mothers.sequence_index, np.arange(399252))
                or not np.array_equal(mothers.u_date, np.asarray(calendar)[mothers.u_index.to_numpy()])):
            raise ValueError('full_original_mother_identity')
        save_csv('full_mothers_projection.csv.gz', mothers)
        actions = read_actions_once(inputs['original_actions'], mothers, counts)
        # One compact, complete original-action training projection is a reusable audit asset.
        save_csv('action_training_projection.csv.gz', actions[original().ACTION_COLUMNS])
        # One original NPZ byte stream is both the reproducibility copy and the
        # input to the only matrix unpack. Reviewers consume this derived copy.
        common_bytes = Path(inputs['original_common']['path']).read_bytes()
        with (out/'common26.npz').open('xb') as stream:
            stream.write(common_bytes)
        artifacts['common26'] = binding(out/'common26.npz')
        if (artifacts['common26']['bytes'] != inputs['original_common']['bytes']
                or artifacts['common26']['sha256'] != inputs['original_common']['sha256']):
            raise ValueError('common_reproduction_copy_identity')
        with np.load(io.BytesIO(common_bytes), allow_pickle=False) as z:
            common = z['common']; columns = z['columns'].tolist()
        del common_bytes
        counts['common_reads'] += 1
        if common.shape != (1552456, 26) or columns != original().COMMON:
            raise ValueError('full_original_common26_identity')
        score_arrays = reuse_scores_once(inputs['original130_scores'], actions, counts)
        save_json('input_phase_checkpoint.json', dict(status='completed', counters=dict(counts),
            full_mothers_projection=artifacts['full_mothers_projection'], action_training_projection=artifacts['action_training_projection']))
        for cell in annual_plan():
            def fit_new(c):
                return fit_new_cell(actions, mothers, common, c, out, counts)
            def reuse_old(c):
                scope, cutoff = c['scope'], c['training_cutoff']
                _, pred, parent = fold_slices(actions, mothers, c); pi = pred.sequence_index.to_numpy()
                values = score_arrays[scope][pi]
                if not np.isfinite(values).all():
                    raise ValueError('complete_exact_reused_annual_scores')
                r = next(r for r in records if (r['scope'], r['cutoff']) == (scope, cutoff))
                counts['reused_fits'] += 1
                return pi, values, dict(r, cutoff=cutoff, training_cutoff=cutoff, reused=True,
                    original_fit_record=r, prediction_children=len(pred), prediction_mothers=len(parent),
                    reused_score_binding=inputs['original130_scores'], reused_prediction_year=int(cutoff[:4]))
            pi, values, record = dispatch_cell(cell, fit_new, reuse_old)
            scope = cell['scope']
            if not cell['reused'] and np.isfinite(score_arrays[scope][pi]).any():
                raise ValueError('annual_scores_already_assigned')
            score_arrays[scope][pi] = values; folds.append(record)
        if counts['fit_attempted'] != 15 or counts['fit_completed'] != 15 or counts['reused_fits'] != 6:
            raise ValueError('exact_15new_6reused_fit_budget')
        save_json('fit_records.json', folds)
        save_json('fit_phase_checkpoint.json', dict(status='completed', fit_records=artifacts['fit_records'], counters=dict(counts)))
        forward = mothers.loc[mothers.u_date.ge('2020-01-01') & mothers.u_date.le(END)].reset_index(drop=True)
        if len(forward) != 161014:
            raise ValueError('full_forward_mother_domain')
        choices = []; summaries = []; boundaries = {}
        forward_mask = actions.u_date.ge('2020-01-01') & actions.u_date.le(END)
        child_path = out/'child_scores.csv.gz'
        with gzip.open(child_path, 'xt', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=selector().SCORE_FIELDS+['training_cutoff', 'deployment_fold_cutoff', 'candidate'])
            writer.writeheader()
            for scope in SCOPES:
                mask = forward_mask if scope == 'main' else forward_mask & actions.family_id.map(original().family_group).eq(int(scope[-1]))
                seqs = actions.loc[mask, 'sequence_index'].to_numpy()
                if not np.isfinite(score_arrays[scope][seqs]).all() or np.isfinite(score_arrays[scope][~mask.to_numpy()]).any():
                    raise ValueError('complete_annual_score_domain_'+scope)
                def rows():
                    for start in range(0, len(seqs), 50000):
                        ii = seqs[start:start+50000]
                        fields = [k for k in selector().SCORE_FIELDS if k not in ('score', 'scope', 'cutoff')]
                        chunk = actions.iloc[ii][fields].copy(); chunk['score'] = score_arrays[scope][ii]
                        chunk['scope'] = scope; chunk['cutoff'] = np.where(chunk.u_date.lt('2023-01-01'), '2020-01-01', '2023-01-01')
                        chunk['training_cutoff'] = chunk.u_date.str[:4]+'-01-01'
                        chunk['deployment_fold_cutoff'] = chunk.cutoff; chunk['candidate'] = CANDIDATE
                        for row in chunk.to_dict('records'):
                            writer.writerow(row); counts['output_child_rows'] += 1; yield row
                parents = forward if scope == 'main' else forward.loc[forward.family_id.map(original().family_group).eq(int(scope[-1]))]
                result = select_scope(parents.to_dict('records'), rows(), scope, calendar)
                choices.append(pd.DataFrame(result['choices'])); summaries.append(dict(scope=scope, **result['summary']))
                for epoch, value in result['boundaries'].items():
                    if epoch in boundaries and boundaries[epoch] != value:
                        raise ValueError('common_K_boundary_changed')
                    boundaries[epoch] = value
                print(json.dumps(dict(phase='annual_selection_complete', scope=scope, parents=len(parents))), flush=True)
        artifacts['child_scores'] = binding(child_path)
        if counts['output_child_rows'] != 1933480:
            raise ValueError('full_annual_child_output_domain')
        allchoices = pd.concat(choices, ignore_index=True)
        main = allchoices.loc[allchoices.scope.eq('main')].sort_values('sequence_index', kind='stable').reset_index(drop=True)
        held = allchoices.loc[allchoices.scope.ne('main')].sort_values('sequence_index', kind='stable').reset_index(drop=True)
        for frame in (main, held):
            if len(frame) != 161014 or frame.event_id.tolist() != forward.event_id.tolist():
                raise ValueError('full_annual_choices_parent_domain')
        control = read_control(control_inputs['control_choices_main'], forward)
        control_held = read_control(control_inputs['control_held_choices'], forward, held=True)
        counts['control_choice_reads'] += 2
        changed_main = int(np.count_nonzero(main.chosen_action_id.to_numpy() != control.chosen_action_id.to_numpy()))
        changed_held = int(np.count_nonzero(held.chosen_action_id.to_numpy() != control_held.chosen_action_id.to_numpy()))
        unchanged_year_checks = []
        for name, candidate, old in [('main', main, control), ('held_union', held, control_held)]:
            for year in REUSE_YEARS:
                mask = candidate.u_date.str[:4].eq(str(year))
                for key in ('chosen_action_id', 'chosen_epoch', 'chosen_action_sequence_index', 'selected'):
                    if candidate.loc[mask, key].tolist() != old.loc[mask, key].tolist():
                        raise ValueError('reused_annual_choice_changed_'+name+'_'+str(year)+'_'+key)
                unchanged_year_checks.append(dict(scope=name, year=year, rows=int(mask.sum()), exact_choice_identity=True))
        paired = pd.concat([control_held.assign(arm='A'), held.assign(arm='B')], ignore_index=True)
        diagnostic, daily, _ = original().held_diagnostics(paired, actions)
        diagnostic.update(schema='stage470_annual_mature_held_original_first_exit_v1', candidate=CANDIDATE,
            control='COMMON52_TWO_CUTOFFS_SAME_K', target='original129 first-exit net_R_stress; not K cash',
            not_cash_admission_veto=True, labels_from_original_single_action_stream=True)
        for g in diagnostic['groups'].values():
            g['known_nonharm'] = bool(g['known_u_equal_mean_increment_R'] is not None and g['known_u_equal_mean_increment_R'] >= 0)
        diagnostic['both_groups_known_nonharm'] = all(diagnostic['groups'][s]['known_nonharm'] for s in SCOPES[1:])
        diagnostic['any_differential_unknown'] = any(diagnostic['groups'][s]['unknown_differential_selected_events'] for s in SCOPES[1:])
        save_csv('choices_main.csv.gz', main); save_csv('choices_held.csv.gz', held)
        artifacts['choices_holdout'] = artifacts['choices_held']
        save_json('held_diagnostic.json', diagnostic); save_csv('held_daily.csv.gz', daily)
        save_json('boundaries.json', dict(schema='stage156_voluntary_K_only_v1', epochs=boundaries,
            policy_version=selector().POLICY_VERSION, sample_end=END, calendar=calendar_b, account_deadline_certified=False))
        selected_ids = set(main.loc[main.selected.eq(1), 'chosen_action_id'])
        selected = actions.loc[actions.action_id.isin(selected_ids), CASH_FIELDS].copy()
        if selected.action_id.duplicated().any() or set(selected.action_id) != selected_ids:
            raise ValueError('complete_selected_cash_actions_required')
        save_csv('selected_actions.csv.gz', selected)
        save_json('selection_summary.json', dict(scopes=summaries, changed_main_parent_choices=changed_main,
            changed_held_parent_choices=changed_held, reused_same_year_checks=unchanged_year_checks,
            original_common_K_and_family_priority=True, no_annual_account_reset=True,
            cash_skip_decision_deferred_to_full_assembled_signal_comparison=True))
        after = {k: inherited_stat(v) for k, v in large.items()}
        if before != after or source_bundle() != bundle:
            raise ValueError('source_or_inherited_inputs_changed_during_actual')
        save_json('source_read_receipt.json', dict(before=before, after=after, counters=dict(counts),
            action_usecols=action_columns(), original_actions_rehashed=False, original_common_rehashed=False))
        save_json('selection_phase_checkpoint.json', dict(status='completed', choices_main=artifacts['choices_main'],
            choices_held=artifacts['choices_held'], counters=dict(counts)))
        status = 'completed'
    except BaseException as exc:
        error = type(exc).__name__+': '+str(exc)
        raise
    finally:
        terminal = save_json('actual_terminal.json', dict(status=status, exit_code=0 if status == 'completed' else 1,
            elapsed_seconds=time.monotonic()-started, error=error, counters=dict(counts), automatic_retry=False,
            new_model_fit_calls=counts['fit_completed'], new_cash_accounts=0, financial_metrics=None,
            production_qualified=False, goal_complete=False))
        manifest = dict(schema='stage470_annual_mature_fit_select_manifest_v1', status=status,
            candidate=CANDIDATE, protocol=pb, protocol_sha256=PROTOCOL_SHA, authorization=ab,
            source_bundle=bundle, input_bindings=inputs, control_inputs=control_inputs, artifacts=artifacts,
            folds=folds, fit_records=artifacts.get('fit_records'), terminal=terminal, counters=dict(counts),
            new_model_fit_calls=counts['fit_completed'], reused_fits=counts['reused_fits'], new_cash_accounts=0,
            changed_main_parent_choices=changed_main, changed_held_parent_choices=changed_held,
            original_four_forward_accounts_modified=False, production_qualified=False, goal_complete=False)
        manifest_b = write_json(out/'manifest.json', manifest)
        if status == 'completed':
            write_json(out/'cash_handoff.json', dict(schema='stage470_annual_mature_cash_handoff_v1',
                status='completed', candidate=CANDIDATE, protocol_sha256=PROTOCOL_SHA,
                protocol_binding=pb, fit_manifest_binding=manifest_b,
                main_choices_binding=artifacts['choices_main'], held_diagnostic_binding=artifacts['held_diagnostic'],
                full_mothers_projection_binding=artifacts['full_mothers_projection'],
                selected_actions_binding=artifacts['selected_actions'], boundaries_binding=artifacts['boundaries'],
                calendar_binding=artifacts['calendar'], calendar_original_binding=calendar_b))
    return dict(status=status, output=str(out), new_model_fit_calls=counts['fit_completed'],
                reused_fits=counts['reused_fits'], new_cash_accounts=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--output', required=True)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
