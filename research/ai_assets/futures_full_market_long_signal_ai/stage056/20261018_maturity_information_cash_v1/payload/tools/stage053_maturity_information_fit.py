"""Stage052 fixed mature-label three-arm HGB experiment (27 actual fits).

Only normalized Stage049 and S11 X columns from Stage009 are read. No native
database, raw OHLC, cash replay, feature/label rebuilding, or model search.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

for _key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_key] = '1'

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_info, threadpool_limits

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE / 'outputs/stage052_maturity_information_cash_protocol/protocol.json'
PROTOCOL_SHA = '968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c'
OWN = ['r1_atr', 'r5_atr', 'r20_atr', 'body_atr', 'range_atr', 'close_location',
       'gap_atr', 'compression5_20', 'log_volume_ratio20', 'breakout20_atr', 'atr_pct']
MATURITY = ['normalizer', 'peer_count', 'tenor_span_years', 'return_mean', 'return_std',
            'return_min', 'return_max', 'front_next_basis_u', 'front_next_basis_prev',
            'front_next_tenor_span_years', 'q_missing', 'front_next_missing', 'normalizer_missing']
COMMON = OWN + MATURITY + ['stress_u_cost_R', 'low20_distance_R']
FEATURE_NAMES = COMMON + [c + '_missing' for c in COMMON] + ['q']
ARMS = ('COMMON', 'ALIGNED', 'SHUFFLED')
SCOPES = (('main', None), ('holdout_0', 0), ('holdout_1', 1))
CUTOFFS = ('2020-01-01', '2023-01-01', '2026-01-01')
PARAMETERS = dict(loss='squared_error', learning_rate=.05, max_iter=100,
                  max_leaf_nodes=7, max_depth=3, min_samples_leaf=100,
                  l2_regularization=1., max_bins=127, max_features=1.,
                  categorical_features=None, early_stopping=False,
                  warm_start=False, random_state=20261018)
IDENTITY = ['event_id', 'product_id', 'family_id', 'u_date', 'u_index']
LABEL_COLUMNS = IDENTITY + ['reference_epoch', 'entry_index', 'exit_index', 'entry_date', 'exit_date',
    'label_known_date', 'label_state', 'net_R_stress', 'label_history_ready20',
    'stress_u_fee_roundtrip_per_lot', 'stress_u_slippage_roundtrip_per_lot',
    'cash_risk_unit', 'u_close', 'low20_u', 'N_u']


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def file_binding(path, role=None):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    result = dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())
    if role:
        result.update(role=role, raw_ohlc=False, reproducibility_required=True)
    return result


def read_bound(binding):
    raw = Path(binding['path']).read_bytes()
    if sha_bytes(raw) != binding['sha256'] or len(raw) != binding['bytes']:
        raise ValueError('input binding mismatch: ' + binding['path'])
    return raw


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def write_csv(path, frame):
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    frame.to_csv(path, index=False, compression={'method': 'gzip', 'mtime': 0}, float_format='%.17g')
    return file_binding(path)


def family_group(family):
    return int(hashlib.sha256(str(family).encode()).hexdigest(), 16) % 2


def training_slice(frame, cutoff, held_group=None):
    use = (frame.label_state.eq('closed_complete_bar_model') & frame.u_date.lt(cutoff)
           & frame.label_known_date.ne('') & frame.label_known_date.lt(cutoff))
    if held_group is not None:
        use &= frame.family_id.map(family_group).ne(held_group)
    train = frame.loc[use].sort_values(['u_date', 'event_id']).copy()
    if len(train) and (not np.isfinite(train.net_R_stress.to_numpy(float)).all()):
        raise ValueError('mature training target is not finite')
    return train


def prediction_slice(frame, cutoff, next_cutoff=None, held_group=None):
    use = frame.u_date.ge(cutoff)
    if next_cutoff is not None:
        use &= frame.u_date.lt(next_cutoff)
    if held_group is not None:
        use &= frame.family_id.map(family_group).eq(held_group)
    return frame.loc[use].sort_values(['u_date', 'event_id']).copy()


def training_weights(train):
    """Compute interval uniqueness strictly inside this mature training set."""
    if train.empty:
        raise ValueError('empty mature training set')
    starts = train.entry_index.to_numpy(float)
    ends = train.exit_index.to_numpy(float)
    if (not np.isfinite(starts).all() or not np.isfinite(ends).all()
            or (starts < 0).any() or (ends < starts).any()
            or not np.equal(starts, starts.astype(np.int64)).all()
            or not np.equal(ends, ends.astype(np.int64)).all()):
        raise ValueError('invalid closed source-calendar interval')
    starts, ends = starts.astype(np.int64), ends.astype(np.int64)
    uniqueness = np.empty(len(train), dtype=float)
    family = train.family_id.to_numpy()
    for name in pd.unique(family):
        positions = np.flatnonzero(family == name)
        a, b = starts[positions], ends[positions]
        delta = np.zeros(int(b.max()) + 2, dtype=np.int64)
        np.add.at(delta, a, 1)
        np.add.at(delta, b + 1, -1)
        concurrency = np.cumsum(delta)[:-1]
        inverse = np.divide(1., concurrency, out=np.zeros_like(concurrency, dtype=float), where=concurrency > 0)
        cumulative = np.r_[0., np.cumsum(inverse)]
        uniqueness[positions] = (cumulative[b + 1] - cumulative[a]) / (b - a + 1)
    u_sum = pd.Series(uniqueness).groupby(train.u_date.to_numpy()).transform('sum').to_numpy()
    date_normalized = uniqueness / u_sum
    weights = date_normalized / date_normalized.mean()
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('nonpositive uniqueness weights')
    return pd.DataFrame(dict(uniqueness=uniqueness, u_normalized_weight=date_normalized,
                             sample_weight=weights), index=train.index)


def _finite_stats(values, weights):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    finite = np.isfinite(x)
    if not finite.any():
        return 0., 0., 1., 0
    mean = float(np.average(x[finite], weights=w[finite]))
    var = float(np.average((x[finite] - mean) ** 2, weights=w[finite]))
    return mean, var, math.sqrt(var) if var > 0 else 1., int(finite.sum())


def fit_scalers(common, q_aligned, q_shuffled, weights):
    x = np.asarray(common, dtype=float)
    w = np.asarray(weights, dtype=float)
    qa, qs = np.asarray(q_aligned, dtype=float), np.asarray(q_shuffled, dtype=float)
    if x.shape != (len(w), 26) or qa.shape != w.shape or qs.shape != w.shape or not len(w):
        raise ValueError('invalid common26/q/weight shapes')
    if not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError('invalid scaler weights')
    stats = [_finite_stats(x[:, j], w) for j in range(26)]
    qm, qv, qscale, qcount = _finite_stats(np.r_[qa, qs], np.r_[w * .5, w * .5])
    return dict(common=dict(columns=COMMON, mean=[v[0] for v in stats], var=[v[1] for v in stats],
                            scale=[v[2] for v in stats], finite_count=[v[3] for v in stats]),
                q=dict(mean=qm, var=qv, scale=qscale, finite_count=qcount),
                weighting='mature training only; common finite weighted population; aligned/shuffled each half weight',
                missing='impute training mean before scaling; common26 missing indicators retained unscaled',
                feature_names=FEATURE_NAMES)


def cell_preprocessing(train):
    weights = training_weights(train)
    scalers = fit_scalers(train[COMMON].to_numpy(float), train.q_aligned.to_numpy(float),
                          train.q_shuffled.to_numpy(float), weights.sample_weight.to_numpy())
    return weights, scalers


def design_matrix(frame, arm, scalers):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    x = frame[COMMON].to_numpy(float)
    missing = ~np.isfinite(x)
    means = np.asarray(scalers['common']['mean'])
    scales = np.asarray(scalers['common']['scale'])
    common = (np.where(missing, means, x) - means) / scales
    q = np.zeros(len(frame)) if arm == 'COMMON' else frame['q_' + arm.lower()].to_numpy(float)
    qscale = scalers['q']
    q = (np.where(np.isfinite(q), q, qscale['mean']) - qscale['mean']) / qscale['scale']
    result = np.column_stack([common, missing.astype(float), q])
    if result.shape != (len(frame), 53) or not np.isfinite(result).all():
        raise ValueError('nonfinite or non53-slot design')
    return result


def prediction_frame(frame, scores, scope, arm, cutoff):
    score = np.asarray(scores, dtype=float)
    if score.shape != (len(frame),):
        raise ValueError('prediction shape mismatch')
    result = frame[IDENTITY].copy()
    result['scope'], result['arm'], result['cutoff'] = scope, arm, cutoff
    result['score'] = score
    result['history_ready20'] = frame.label_history_ready20.to_numpy(dtype=np.int8)
    result['selected'] = (result.history_ready20.eq(1).to_numpy() & np.isfinite(score) & (score > 0)).astype(np.int8)
    return result[IDENTITY + ['scope', 'arm', 'cutoff', 'score', 'selected', 'history_ready20']]


def make_estimator():
    if sklearn.__version__ != '1.6.1':
        raise ValueError('fixed experiment requires sklearn1.6.1')
    return HistGradientBoostingRegressor(**PARAMETERS)


def portable_model(model):
    """HGB numeric nodes contain already-shrunk leaf values in sklearn1.6.1."""
    trees = []
    for predictors in model._predictors:
        if len(predictors) != 1:
            raise ValueError('only one squared-error regression tree per iteration is allowed')
        nodes = predictors[0].nodes
        if nodes['is_categorical'].any():
            raise ValueError('categorical tree outside fixed protocol')
        fields = ('value', 'feature_idx', 'num_threshold', 'missing_go_to_left', 'left', 'right', 'is_leaf')
        tree = []
        for record in nodes:
            tree.append({key: (float(record[key]) if key in ('value', 'num_threshold') else int(record[key]))
                         for key in fields})
        trees.append(tree)
    return dict(schema='stage053_portable_numeric_hgb_v1', sklearn_version=sklearn.__version__,
                loss='squared_error', link='identity', baseline=float(model._baseline_prediction.item()),
                formula='baseline + sum(reached_leaf.value for every tree); DO NOT multiply learning_rate again',
                leaf_values_include_learning_rate=True, learning_rate=.05,
                n_features=53, feature_names=FEATURE_NAMES, trees=trees)


def _log(stream, value):
    stream.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def run_matrix(frame, output, *, estimator_factory=make_estimator, execution_kind='actual', counters=None):
    """Persist each fit before proceeding; injected estimation permits finite orchestration tests."""
    output = Path(output)
    if execution_kind not in ('actual', 'synthetic_fixture'):
        raise ValueError('unknown execution kind')
    counters = counters if counters is not None else dict(fit_calls_started=0, fit_calls_completed=0)
    predictions = {name: [] for name, _ in SCOPES}
    fit_records = []
    with (output / 'fit_log.jsonl').open('x') as log:
        for cutoff_i, cutoff in enumerate(CUTOFFS):
            next_cutoff = CUTOFFS[cutoff_i + 1] if cutoff_i + 1 < len(CUTOFFS) else None
            for scope, held in SCOPES:
                train = training_slice(frame, cutoff, held)
                test = prediction_slice(frame, cutoff, next_cutoff, held)
                if train.empty or test.empty:
                    raise ValueError('empty training/prediction cell: ' + scope + ' ' + cutoff)
                weights, scalers = cell_preprocessing(train)
                for arm in ARMS:
                    fit_id = f'{cutoff[:4]}_{scope}_{arm}'
                    fit_dir = output / 'fits' / fit_id
                    fit_dir.mkdir(parents=True, exist_ok=False)
                    weight_frame = train[IDENTITY + ['reference_epoch', 'entry_index', 'exit_index',
                        'entry_date', 'exit_date', 'label_known_date', 'label_state', 'net_R_stress']].copy()
                    for col in weights:
                        weight_frame[col] = weights[col].to_numpy()
                    weight_binding = write_csv(fit_dir / 'training_weights.csv.gz', weight_frame)
                    write_json(fit_dir / 'scaler.json', scalers)
                    x = design_matrix(train, arm, scalers)
                    model = estimator_factory()
                    counters['fit_calls_started'] += 1
                    started = time.monotonic()
                    print(f"fit {counters['fit_calls_started']}/27 START {fit_id} train={len(train)} test={len(test)}", flush=True)
                    _log(log, dict(event='fit_started', fit_id=fit_id, execution_kind=execution_kind,
                                   train_rows=len(train), test_rows=len(test), **counters))
                    with threadpool_limits(limits=1):
                        model.fit(x, train.net_R_stress.to_numpy(float),
                                  sample_weight=weights.sample_weight.to_numpy())
                    counters['fit_calls_completed'] += 1
                    joblib.dump(model, fit_dir / 'model.joblib', compress=3)
                    write_json(fit_dir / 'portable_model.json', portable_model(model))
                    with threadpool_limits(limits=1):
                        scores = model.predict(design_matrix(test, arm, scalers))
                    if not np.isfinite(scores).all():
                        raise ValueError('estimator produced nonfinite scores')
                    predictions[scope].append(prediction_frame(test, scores, scope, arm, cutoff))
                    record = dict(fit_id=fit_id, scope=scope, arm=arm, cutoff=cutoff,
                        next_cutoff_exclusive=next_cutoff, held_family_group=held,
                        training_rows=len(train), prediction_rows=len(test),
                        training_dates=int(train.u_date.nunique()), training_family_ids=sorted(train.family_id.unique()),
                        max_u_date=str(train.u_date.max()), max_label_known_date=str(train.label_known_date.max()),
                        training_ids_sha256=sha_bytes(('\n'.join(train.event_id) + '\n').encode()),
                        training_weights=weight_binding, scaler=file_binding(fit_dir / 'scaler.json'),
                        model=file_binding(fit_dir / 'model.joblib'), portable_model=file_binding(fit_dir / 'portable_model.json'),
                        head_dimension=53, elapsed_seconds=time.monotonic() - started)
                    write_json(fit_dir / 'fit.json', record)
                    fit_records.append(record)
                    _log(log, dict(event='fit_completed', execution_kind=execution_kind, **record, **counters))
                    print(f"fit {counters['fit_calls_completed']}/27 DONE {fit_id} seconds={record['elapsed_seconds']:.3f}", flush=True)
                    del model, x
    bindings = {}
    for scope, parts in predictions.items():
        combined = pd.concat(parts, ignore_index=True).sort_values(['arm', 'u_date', 'event_id'])
        if combined.duplicated(['event_id', 'arm']).any():
            raise ValueError('duplicate prediction identity')
        bindings[scope] = write_csv(output / f'predictions_{scope}.csv.gz', combined)
    held = pd.concat(predictions['holdout_0'] + predictions['holdout_1'], ignore_index=True)
    held = held.sort_values(['arm', 'u_date', 'event_id'])
    if held.duplicated(['event_id', 'arm']).any():
        raise ValueError('duplicate combined held identity')
    bindings['holdout_combined'] = write_csv(output / 'predictions_holdout_combined.csv.gz', held)
    return dict(**counters, actual_fit_calls_started=counters['fit_calls_started'] if execution_kind == 'actual' else 0,
                actual_fit_calls_completed=counters['fit_calls_completed'] if execution_kind == 'actual' else 0,
                execution_kind=execution_kind, predictions=bindings, fits=fit_records,
                fit_log=file_binding(output / 'fit_log.jsonl'))


def load_protocol():
    raw = PROTOCOL.read_bytes()
    if sha_bytes(raw) != PROTOCOL_SHA:
        raise ValueError('frozen052 protocol SHA changed')
    protocol = json.loads(raw)
    if (protocol['common_columns'] != COMMON or protocol['head_dimension'] != 53
            or protocol['arms'] != list(ARMS) or protocol['cutoffs'] != list(CUTOFFS)
            or protocol['scopes'] != [name for name, _ in SCOPES]
            or protocol['actual_fit_calls_expected'] != 27 or protocol['threads'] != 1
            or protocol['target'] != 'net_R_stress'):
        raise ValueError('unexpected Stage052 contract')
    expected = {k: v for k, v in protocol['estimator'].items() if k not in ('class', 'sklearn_version')}
    if expected != PARAMETERS or protocol['estimator']['sklearn_version'] != sklearn.__version__:
        raise ValueError('estimator or runtime differs from frozen052')
    for name in ('design_document', 'accepted_decision', 'data_manifest', 'data_review', 'own_features_manifest'):
        read_bound(protocol[name])
    return protocol


def _csv_projection(binding, columns):
    raw = read_bound(binding)  # hashes normalized bytes once; never opens native database
    frame = pd.read_csv(io.BytesIO(raw), compression='gzip' if binding['path'].endswith('.gz') else None,
                        usecols=columns, dtype=str, keep_default_na=False)
    if set(frame) != set(columns):
        raise ValueError('projection schema changed')
    return frame


def load_inputs(protocol):
    labels = _csv_projection(protocol['labels'], LABEL_COLUMNS)
    maturity = _csv_projection(protocol['maturity_features'], IDENTITY + MATURITY + ['q_aligned', 'q_shuffled'])
    own = _csv_projection(protocol['own_features'], ['event_id'] + OWN)
    expected = protocol['scope']['panel_rows']
    for name, frame in (('labels', labels), ('maturity', maturity), ('own_s11_X_only', own)):
        if len(frame) != expected or frame.event_id.duplicated().any():
            raise ValueError('mother identity/row count differs: ' + name)
    if labels.duplicated(['product_id', 'u_date']).any():
        raise ValueError('duplicate mother product/date')
    for key in IDENTITY:
        if not labels[key].equals(maturity[key]):
            raise ValueError('049 feature/label identity differs: ' + key)
    if set(own.event_id) != set(labels.event_id):
        raise ValueError('009 S11 event identity differs')
    frame = labels.merge(maturity.drop(columns=[k for k in IDENTITY if k != 'event_id']),
                         on='event_id', validate='one_to_one', sort=False)
    frame = frame.merge(own, on='event_id', validate='one_to_one', sort=False)
    numeric = ['u_index', 'entry_index', 'exit_index', 'net_R_stress', 'label_history_ready20',
        'stress_u_fee_roundtrip_per_lot', 'stress_u_slippage_roundtrip_per_lot', 'cash_risk_unit',
        'u_close', 'low20_u', 'N_u'] + OWN + MATURITY + ['q_aligned', 'q_shuffled']
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column].replace('', np.nan), errors='raise')
    if not frame.label_history_ready20.isin([0, 1]).all() or frame.u_index.isna().any():
        raise ValueError('invalid ready/source index')
    frame['u_index'] = frame.u_index.astype(np.int32)
    frame['label_history_ready20'] = frame.label_history_ready20.astype(np.int8)
    if not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all():
        raise ValueError('ordinary/F family identity differs')
    with np.errstate(invalid='ignore', divide='ignore'):
        frame['stress_u_cost_R'] = ((frame.stress_u_fee_roundtrip_per_lot + frame.stress_u_slippage_roundtrip_per_lot)
                                    / frame.cash_risk_unit)
        frame['low20_distance_R'] = (frame.u_close - frame.low20_u) / (2 * frame.N_u)
    if int(frame.u_date.ge(CUTOFFS[0]).sum()) != 161014:
        raise ValueError('2020+ mother rows changed')
    closed = frame.label_state.eq('closed_complete_bar_model')
    if int(closed.sum()) != 180507 or frame.loc[~closed, 'net_R_stress'].notna().any():
        raise ValueError('closed/null label contract changed')
    if frame.loc[closed, 'label_known_date'].eq('').any() or not frame.loc[closed, 'label_known_date'].gt(frame.loc[closed, 'u_date']).all():
        raise ValueError('closed label maturity invalid')
    return frame


def save_prepared_common(frame, output):
    """Small normalized accepted X projection; old009 targets are never copied."""
    output = Path(output)
    values = frame[COMMON].to_numpy(dtype=np.float64)
    values[~np.isfinite(values)] = np.nan
    path = output / 'prepared_common.npz'
    with path.open('xb') as stream:
        np.savez_compressed(stream, common=values, columns=np.asarray(COMMON, dtype='U64'))
    identity = dict(rows=len(frame), columns=COMMON, dtype='float64', order='original049_mother_order',
        event_ids_sha256=sha_bytes(('\n'.join(frame.event_id) + '\n').encode()),
        event_id_fingerprint_encoding='utf8 each event_id plus newline, including final newline',
        common=file_binding(path, 'normalized_common_model_input'),
        nonfinite='NaN; imputation/scaling still mature-training-only', raw_ohlc=False,
        old009_parsed_columns=['event_id'] + OWN, old009_labels_masks_predictions_parsed=False)
    write_json(output / 'prepared_common_identity.json', identity)
    return identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    args = parser.parse_args(argv)
    if args.protocol_sha256 != PROTOCOL_SHA:
        raise ValueError('explicit frozen052 SHA required')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    counters = dict(fit_calls_started=0, fit_calls_completed=0)
    start = time.monotonic()
    write_json(out / 'actual_started.json', dict(status='started', actual_start_count=1,
        started_at_utc=datetime.now(timezone.utc).isoformat(), protocol=file_binding(PROTOCOL),
        source=file_binding(__file__), actual_fit_calls_started=0, actual_fit_calls_completed=0,
        native_source_queries=0, new_cash_accounts=0))
    try:
        protocol = load_protocol()
        source = file_binding(__file__, 'experiment_source')
        tests = file_binding(Path(__file__).with_name('test_stage053_maturity_information_fit.py'), 'contract_tests')
        frame = load_inputs(protocol)
        prepared_common = save_prepared_common(frame, out)
        write_json(out / 'input_bindings.json', dict(protocol=file_binding(PROTOCOL, 'feature_contract'),
            inputs={name: {**protocol[name], 'role': role, 'raw_ohlc': False, 'reproducibility_required': True}
                    for name, role in [('labels', 'economic_event_labels'), ('maturity_features', 'feature_matrix'),
                                       ('own_features', 'common_s11_X_projection_source')]},
            source=source, tests=tests, prepared_common=prepared_common,
            own_features_parsed_columns=['event_id'] + OWN,
            database_read=False, database_hashed=False, raw_native_saved=False))
        write_json(out / 'versions.json', dict(python=sys.version, platform=platform.platform(),
            sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__,
            joblib=joblib.__version__, estimator_defaults=make_estimator().get_params(),
            thread_environment={k: os.environ[k] for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')}, threadpools=threadpool_info()))
        result = run_matrix(frame, out, counters=counters)
        if result['actual_fit_calls_started'] != 27 or result['actual_fit_calls_completed'] != 27:
            raise ValueError('actual fit budget differs from27')
        expected = set(frame.loc[frame.u_date.ge(CUTOFFS[0]), 'event_id'])
        for scope in ('main', 'holdout_combined'):
            prediction = pd.read_csv(result['predictions'][scope]['path'], usecols=['event_id', 'arm'])
            if len(prediction) != 3 * len(expected) or any(set(prediction.loc[prediction.arm.eq(a), 'event_id']) != expected for a in ARMS):
                raise ValueError('prediction mother coverage differs')
        terminal = dict(status='completed', exit_code=0, actual_start_count=1, completed_actual_runs=1,
            actual_fit_calls_started=counters['fit_calls_started'], actual_fit_calls_completed=counters['fit_calls_completed'],
            native_source_queries=0, new_cash_accounts=0, elapsed_seconds=time.monotonic() - start,
            goal_complete=False, production_qualified=False)
        role = lambda p: ('model_artifact' if p.name == 'model.joblib' else 'portable_model' if p.name == 'portable_model.json'
            else 'training_weights_and_intervals' if p.name == 'training_weights.csv.gz'
            else 'training_scaler' if p.name == 'scaler.json' else 'predictions' if p.name.startswith('predictions_')
            else 'qualification_evidence' if p.name in ('actual_started.json', 'actual_terminal.json')
            else 'normalized_common_model_input' if p.name == 'prepared_common.npz'
            else 'normalized_common_identity' if p.name == 'prepared_common_identity.json'
            else 'feature_contract' if p.name == 'input_bindings.json' else 'runtime_versions' if p.name == 'versions.json'
            else 'fit_receipt')
        artifacts = [file_binding(p, role(p)) for p in sorted(out.rglob('*')) if p.is_file()]
        # Bind the final terminal bytes before publication; terminal is written
        # last, so any earlier exception leaves an explicit failed terminal.
        terminal_bytes = (json.dumps(terminal, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        terminal_binding = dict(path=str(out / 'actual_terminal.json'), bytes=len(terminal_bytes),
            sha256=sha_bytes(terminal_bytes), role='qualification_evidence', raw_ohlc=False, reproducibility_required=True)
        artifacts.append(terminal_binding)
        manifest = dict(schema='stage053_maturity_information_fit_v1', **{**terminal, **result},
            protocol=file_binding(PROTOCOL), source=source, tests=tests,
            input_bindings=file_binding(out / 'input_bindings.json'), versions=file_binding(out / 'versions.json'),
            inputs={name: protocol[name] for name in ('labels', 'maturity_features', 'own_features', 'data_manifest', 'data_review')},
            prediction_rows_per_arm_main=161014, prediction_rows_per_arm_held_combined=161014,
            ordinary_F_share_family=True, head_dimension=53, no_2019_scores=True,
            terminal=terminal_binding, prepared_common=prepared_common, artifacts=artifacts, raw_native_saved=False)
        write_json(out / 'manifest.json', manifest)
        write_json(out / 'actual_terminal.json', terminal)
        print(json.dumps(dict(status='completed', manifest=file_binding(out / 'manifest.json'), **counters)), flush=True)
    except BaseException as exc:
        terminal = dict(status='failed', exit_code=1, actual_start_count=1, completed_actual_runs=0,
            actual_fit_calls_started=counters['fit_calls_started'], actual_fit_calls_completed=counters['fit_calls_completed'],
            native_source_queries=0, new_cash_accounts=0, elapsed_seconds=time.monotonic() - start,
            exception_type=type(exc).__name__, exception=str(exc))
        if not (out / 'actual_terminal.json').exists():
            write_json(out / 'actual_terminal.json', terminal)
        raise


if __name__ == '__main__':
    main()
