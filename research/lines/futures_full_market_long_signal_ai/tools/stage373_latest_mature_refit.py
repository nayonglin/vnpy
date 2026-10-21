"""One authorized train-only PURE52 update. No history prediction or cash runner.

prepare reads small code/metadata only. run_actual requires an exact root JSON
binding, then reads the accepted actions and common entities once each. The four
source-bound mathematical functions are AST-extracted without importing runners.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import sys
import time

for _thread_key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS',
                    'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_thread_key] = '1'

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
STAGE_ROOT = LINE/'outputs/stage373_latest_mature_refit'
PROTOCOL = LINE/'outputs/stage372_latest_mature_training_protocol/protocol.json'
PROTOCOL_SHA = 'd854a77e3935f290c554399718f51f8bb775849372d39e8ecd88b9cd72c85001'
CANDIDATE = 'PURE52_LATEST_MATURE_20261020'
CUTOFF = '2026-10-20'
OLD_CUTOFF = '2023-01-01'
SNAPSHOT_END = '2026-10-16'
ROWS = 1552456
OLD_ROWS = 445475
PARAMETERS = dict(alpha=1., fit_intercept=True, solver='cholesky')
READ_COLUMNS = ['sequence_index', 'action_sequence_index', 'action_id', 'event_id',
    'actual_epoch', 'reference_epoch', 'product_id', 'family_id', 'u_date', 'u_index',
    'mother_sequence_index', 'mother_event_id', 'anchor_epoch', 'entry_index',
    'exit_index', 'label_known_date', 'label_state', 'net_R_stress', 'u_action_eligible']
NUMERIC = ['sequence_index', 'action_sequence_index', 'u_index', 'mother_sequence_index',
           'entry_index', 'exit_index', 'net_R_stress', 'u_action_eligible']


def binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def read_bound(item, counters=None, role=None):
    path = Path(item['path'])
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular bound input required: '+str(path))
    if counters is not None:
        counters[role] = counters.get(role, 0)+1
        if counters[role] != 1:
            raise ValueError('more than one entity read: '+role)
    raw = path.read_bytes()
    if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise ValueError('input byte/SHA mismatch: '+str(path))
    return raw


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return binding(path)


def write_csv(path, frame):
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    frame.to_csv(path, index=False, compression={'method': 'gzip', 'mtime': 0},
                 float_format='%.17g')
    return binding(path)


def append_event(path, value):
    with Path(path).open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False)+'\n')
        stream.flush()
        os.fsync(stream.fileno())


def load_protocol():
    item = dict(path=str(PROTOCOL), bytes=7908, sha256=PROTOCOL_SHA)
    value = json.loads(read_bound(item))
    if (value.get('schema') != 'stage372_single_latest_mature_refit_protocol_v1'
            or value.get('candidate') != CANDIDATE or value.get('training_cutoff') != CUTOFF
            or value.get('source_snapshot_end') != SNAPSHOT_END
            or value['population']['old_training_rows_reference'] != OLD_ROWS
            or value['population']['old_cutoff_for_added_count'].split(';', 1)[0] != OLD_CUTOFF
            or value['math']['estimator'] != PARAMETERS
            or value['budgets']['actual_fit_attempts_max'] != 1):
        raise ValueError('fixed372 scope differs')
    return value


def load_math(protocol):
    """Only exact original function ASTs and the COMMON literal may execute."""
    namespace = dict(np=np, pd=pd, math=math, json=json)
    names = {'stage130_contract_choice_fit.py':
                 ('union_intervals', 'training_weights', 'design'),
             'stage071_settlement_narrow_fit.py': ('finite_stats',)}
    columns = None
    for filename, functions in names.items():
        raw = read_bound(protocol['source_math'][filename])
        tree = ast.parse(raw, filename=filename)
        found = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        if not set(functions).issubset(found):
            raise ValueError('original pure math definitions missing')
        if filename.startswith('stage071'):
            assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'COMMON' for t in node.targets)]
            if len(assignments) != 1:
                raise ValueError('unique originalCOMMON literal required')
            columns = ast.literal_eval(assignments[0].value)
            if len(columns) != 26 or len(set(columns)) != 26:
                raise ValueError('original26 columns differ')
        module = ast.Module(body=[found[name] for name in functions], type_ignores=[])
        exec(compile(module, filename, 'exec'), namespace)
    return {name: namespace[name] for functions in names.values() for name in functions}, columns


def source_bundle():
    return sorted([binding(TOOLS/name) for name in (
        'stage373_latest_mature_refit.py', 'test_stage373_latest_mature_refit.py',
        'stage130_contract_choice_fit.py', 'stage071_settlement_narrow_fit.py')],
        key=lambda item: item['path'])


def runtime():
    return dict(python=sys.version, executable=sys.executable,
        packages={name: importlib.metadata.version(name)
                  for name in ('numpy', 'pandas', 'scipy', 'scikit-learn', 'threadpoolctl')},
        thread_limit=1)


def fresh_output(output):
    out = Path(output).resolve()
    if STAGE_ROOT not in out.parents or out.exists():
        raise ValueError('fresh output below stage373 required')
    return out


def prepare(output):
    """Create an unauthorized exact template; never read large training inputs."""
    out = fresh_output(output)
    protocol = load_protocol()
    load_math(protocol)
    bundle = source_bundle()
    manifest = json.loads(read_bound(protocol['inputs']['dataset_manifest']))
    terminal = json.loads(read_bound(protocol['inputs']['dataset_terminal']))
    validate_metadata(manifest, terminal, protocol)
    out.mkdir(parents=True)
    template = dict(schema='stage373_exact_root_fit_authorization_v1',
        authorized_by=None, exact_source_authorized=False, stage='fit',
        candidate=CANDIDATE, scope='main', training_cutoff=CUTOFF,
        protocol=binding(PROTOCOL), source_bundle=bundle,
        input_bindings=protocol['inputs'], output=str(STAGE_ROOT/'actual_run1'),
        actual_fit_attempts_max=1, historical_predictions=0, cash_replays=0,
        no_automatic_retry=True)
    template_binding = write_json(out/'root_authorization_template.json', template)
    return write_json(out/'prepare_receipt.json', dict(
        schema='stage373_fit_only_preparation_v1', status='prepared_not_authorized',
        prepared_at=datetime.now(timezone.utc).isoformat(), protocol=binding(PROTOCOL),
        source_bundle=bundle, input_bindings=protocol['inputs'], runtime=runtime(),
        root_authorization_template=template_binding, large_data_reads=0,
        actual_fit_attempts=0, actual_completed_models=0, predictions=0, cash_replays=0))


def validate_metadata(manifest, terminal, protocol):
    if (manifest.get('schema') != 'stage129_contract_choice_dataset_v1'
            or manifest.get('status') != 'completed' or manifest.get('mode') != 'actual'
            or terminal.get('status') != 'completed' or manifest.get('action_rows') != ROWS):
        raise ValueError('accepted129 complete metadata required')
    for role in ('actions', 'common'):
        if manifest.get(role) != protocol['inputs'][role]:
            raise ValueError('accepted129 '+role+' binding mismatch')


def load_training_inputs(protocol, counters):
    manifest = json.loads(read_bound(protocol['inputs']['dataset_manifest']))
    terminal = json.loads(read_bound(protocol['inputs']['dataset_terminal']))
    validate_metadata(manifest, terminal, protocol)
    raw = read_bound(protocol['inputs']['actions'], counters, 'actions')
    frame = pd.read_csv(io.BytesIO(raw), compression='gzip', usecols=READ_COLUMNS,
        dtype=str, keep_default_na=False, float_precision='round_trip')
    del raw
    for name in NUMERIC:
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    if (len(frame) != ROWS or frame.action_id.duplicated().any()
            or not np.array_equal(frame.sequence_index, np.arange(ROWS))
            or not frame.sequence_index.eq(frame.action_sequence_index).all()
            or not frame.event_id.eq(frame.action_id).all()
            or not frame.reference_epoch.eq(frame.actual_epoch).all()
            or not frame.u_action_eligible.isin([0, 1]).all()):
        raise ValueError('accepted129 full row order/alias mismatch')
    for name in ('action_id', 'product_id', 'family_id', 'actual_epoch'):
        if frame[name].eq('').any():
            raise ValueError('empty action identity: '+name)
    for name in ('u_index', 'mother_sequence_index'):
        values = frame[name].to_numpy(float)
        if not np.isfinite(values).all() or (values < 0).any() or not np.equal(values, np.floor(values)).all():
            raise ValueError('invalid action identity index: '+name)
    for name in ('u_date', 'label_known_date'):
        values = frame[name] if name == 'u_date' else frame.loc[frame[name].ne(''), name]
        if (not values.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all()
                or (values > SNAPSHOT_END).any()):
            raise ValueError('dates outside accepted16 snapshot: '+name)
        pd.to_datetime(values, format='%Y-%m-%d', errors='raise')
    raw = read_bound(protocol['inputs']['common'], counters, 'common')
    with np.load(io.BytesIO(raw), allow_pickle=False) as arrays:
        columns = arrays['columns'].tolist()
        common = arrays['common']
        if common.shape != (ROWS, 26) or common.dtype != np.dtype('float64'):
            raise ValueError('accepted common26 shape/dtype mismatch')
    del raw
    return frame, common, columns


def mature_mask(frame, cutoff):
    return (frame.u_action_eligible.eq(1)
        & frame.label_state.eq('closed_complete_bar_model')
        & frame.u_date.lt(cutoff) & frame.label_known_date.ne('')
        & frame.label_known_date.lt(cutoff) & np.isfinite(frame.net_R_stress))


def build_training(frame, common, kernels, columns):
    """Training-only projection; no prediction set is created or accessed."""
    new_mask, old_mask = mature_mask(frame, CUTOFF), mature_mask(frame, OLD_CUTOFF)
    if (old_mask & ~new_mask).any():
        raise ValueError('old mature pool is not a subset')
    train = frame.loc[new_mask].copy()
    if train.empty:
        raise ValueError('empty mature training')
    ti = train.sequence_index.to_numpy(int)
    weights_frame, groups = kernels['training_weights'](train)
    weights = weights_frame.sample_weight.to_numpy(float)
    stats = [kernels['finite_stats'](common[ti, j], weights) for j in range(26)]
    scaler = dict(common=dict(columns=columns,
        **{key: [item[key] for item in stats] for key in ('mean', 'var', 'scale', 'finite_count')}),
        feature_names=columns+[name+'_missing' for name in columns], scope='main', cutoff=CUTOFF,
        weighting='family_u_interval_union_then_divide_actions_then_equal_u',
        missing='raw nonfinite standardized0 plus missing flag', units='COMMON unchanged original2N')
    record = dict(input_action_rows=len(frame), new_rows=len(train), old_rows=int(old_mask.sum()),
        added_rows=int((new_mask & ~old_mask).sum()), excluded_rows=int((~new_mask).sum()),
        training_dates=int(train.u_date.nunique()), training_families=int(train.family_id.nunique()),
        training_groups=len(groups), max_u_date=str(train.u_date.max()),
        max_label_known_date=str(train.label_known_date.max()), cutoff=CUTOFF,
        old_cutoff=OLD_CUTOFF, dimension=52, source_snapshot_end=SNAPSHOT_END)
    return dict(train=train, weight_columns=weights_frame, groups=groups, weights=weights,
        y=train.net_R_stress.to_numpy(float), x=kernels['design'](common[ti], scaler),
        scaler=scaler, record=record)


def fit_training(problem, on_attempt, on_complete):
    """Exactly one Ridge.fit or no fit when the mature set did not expand."""
    if problem['record']['added_rows'] == 0:
        return None
    estimator = Ridge(**PARAMETERS)
    on_attempt()
    with threadpool_limits(limits=1):
        estimator.fit(problem['x'], problem['y'], sample_weight=problem['weights'])
    on_complete()
    z = np.column_stack([problem['x'], np.ones(len(problem['x']))])
    weights, y = problem['weights'], problem['y']
    lhs = z.T @ (weights[:, None]*z)
    lhs[np.arange(52), np.arange(52)] += 1.
    rhs = z.T @ (weights*y)
    beta = np.r_[estimator.coef_, estimator.intercept_]
    residual = lhs@beta-rhs
    if (not np.isfinite(beta).all()
            or not np.allclose(lhs@beta, rhs, rtol=1e-8, atol=1e-7)):
        raise ValueError('Ridge normal equation check failed; no refit')
    return dict(portable=dict(schema='stage130_shared_portable_ridge_v1', scope='main',
        cutoff=CUTOFF, parameters=PARAMETERS, feature_names=problem['scaler']['feature_names'],
        coef=estimator.coef_.tolist(), intercept=float(estimator.intercept_)),
        normal_equations=dict(lhs=lhs, rhs=rhs, coefficient_with_intercept=beta,
            weight_sum=np.array(weights.sum())),
        max_equation_abs_residual=float(np.max(np.abs(residual))), historical_predictions=0)


def run_actual(auth, output):
    """auth is a root authorization binding {path,bytes,sha256}, not an approval."""
    out = fresh_output(output)
    protocol = load_protocol()
    authorization = json.loads(read_bound(auth))
    bundle = source_bundle()
    if (authorization.get('schema') != 'stage373_exact_root_fit_authorization_v1'
            or authorization.get('authorized_by') != 'root'
            or authorization.get('exact_source_authorized') is not True
            or authorization.get('stage') != 'fit' or authorization.get('candidate') != CANDIDATE
            or authorization.get('scope') != 'main' or authorization.get('training_cutoff') != CUTOFF
            or authorization.get('protocol') != binding(PROTOCOL)
            or authorization.get('source_bundle') != bundle
            or authorization.get('input_bindings') != protocol['inputs']
            or authorization.get('output') != str(out)
            or authorization.get('actual_fit_attempts_max') != 1
            or authorization.get('historical_predictions') != 0
            or authorization.get('cash_replays') != 0
            or authorization.get('no_automatic_retry') is not True):
        raise ValueError('exact root373 scope/source/input/output authorization required')
    kernels, columns = load_math(protocol)
    began, started = datetime.now(timezone.utc).isoformat(), time.monotonic()
    out.mkdir(parents=True)
    counters, attempts, completed = {}, 0, 0
    write_json(out/'actual_started.json', dict(status='started', mode='actual',
        started_at=began, protocol=binding(PROTOCOL), authorization=auth,
        source_bundle=bundle, input_bindings=protocol['inputs'], runtime=runtime()))
    def attempt():
        nonlocal attempts
        attempts += 1
        if attempts != 1:
            raise ValueError('one fit attempt exhausted')
        append_event(out/'fit_attempts.jsonl', dict(attempt=attempts, candidate=CANDIDATE,
            at=datetime.now(timezone.utc).isoformat()))
    def complete():
        nonlocal completed
        completed += 1
        append_event(out/'fit_completed.jsonl', dict(completed=completed, candidate=CANDIDATE,
            at=datetime.now(timezone.utc).isoformat()))
    try:
        frame, common, observed_columns = load_training_inputs(protocol, counters)
        if observed_columns != columns:
            raise ValueError('exact original common column names/order required')
        problem = build_training(frame, common, kernels, columns)
        if problem['record']['old_rows'] != OLD_ROWS:
            raise ValueError('old2023 maturity count differs from accepted445475')
        del frame, common
        train_out = problem['train'].reset_index(drop=True)
        for key in problem['weight_columns']:
            train_out[key] = problem['weight_columns'][key].to_numpy()
        artifacts = dict(training_identity_weights=write_csv(out/'training_identity_weights.csv.gz', train_out),
            weight_groups=write_csv(out/'weight_groups.csv.gz', problem['groups']),
            scaler=write_json(out/'scaler.json', problem['scaler']))
        result = fit_training(problem, attempt, complete)
        if result is None:
            status = 'stopped_no_added_mature_rows'
        else:
            status = 'completed'
            artifacts['portable_model'] = write_json(out/'portable_model.json', result['portable'])
            with (out/'normal_equations.npz').open('xb') as stream:
                np.savez_compressed(stream, **result['normal_equations'])
                stream.flush()
                os.fsync(stream.fileno())
            artifacts['normal_equations'] = binding(out/'normal_equations.npz')
        if source_bundle() != bundle:
            raise ValueError('source changed during actual; no retry')
        record = dict(problem['record'], candidate=CANDIDATE, parameters=PARAMETERS,
            actual_fit_attempts=attempts, actual_completed_models=completed,
            normal_equation_max_abs_residual=result['max_equation_abs_residual'] if result else None,
            historical_predictions=0, selections=0, cash_replays=0, T1=None,
            maturity_exclusions='original mask; unknown/open/censored/cancelled never zero-target')
        artifacts['fit_record'] = write_json(out/'fit_record.json', record)
        terminal = dict(status=status, mode='actual', started_at=began,
            finished_at=datetime.now(timezone.utc).isoformat(), exit_code=0,
            actual_fit_attempts=attempts, actual_completed_models=completed,
            training_entity_reads=counters, historical_predictions=0, selections=0,
            cash_replays=0, SQL=0, downloads=0, automatic_retry=False, T1=None,
            elapsed_seconds=time.monotonic()-started)
        artifacts['terminal'] = write_json(out/'actual_terminal.json', terminal)
        return write_json(out/'manifest.json', dict(schema='stage373_latest_mature_fit_only_v1',
            status=status, candidate=CANDIDATE, protocol=binding(PROTOCOL), authorization=auth,
            source_bundle=bundle, input_bindings=protocol['inputs'], runtime=runtime(),
            artifacts=artifacts, training_entity_reads=counters, fit_record=record,
            alpha_qualified=False, production_qualified=False, T1=None))
    except BaseException as error:
        if not (out/'actual_terminal.json').exists():
            write_json(out/'actual_terminal.json', dict(status='failed', mode='actual', exit_code=1,
                started_at=began, finished_at=datetime.now(timezone.utc).isoformat(),
                actual_fit_attempts=attempts, actual_completed_models=completed,
                training_entity_reads=counters, historical_predictions=0, cash_replays=0,
                error_type=type(error).__name__, error=str(error), automatic_retry=False, T1=None))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--output', required=True)
    actual = sub.add_parser('execute')
    actual.add_argument('--authorization', required=True)
    actual.add_argument('--authorization-sha256', required=True)
    actual.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.output)
    else:
        item = binding(args.authorization)
        if item['sha256'] != args.authorization_sha256:
            raise ValueError('root authorization SHA differs')
        result = run_actual(item, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
