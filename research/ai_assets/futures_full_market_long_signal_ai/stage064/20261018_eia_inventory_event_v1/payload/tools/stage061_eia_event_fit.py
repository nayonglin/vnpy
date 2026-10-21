"""Frozen Stage059 EIA information experiment: two cutoffs, three Ridge heads.

No native SQL, old targets/masks/models, cash replay or source downloads. The
actual CLI needs a root-issued source-bound six-fit authorization; preflight
only projects normalized inputs and computes maturity/scaler diagnostics.
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
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE / 'outputs/stage059_eia_full_market_protocol/protocol.json'
PROTOCOL_SHA = 'ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158'
COMMON = ['stress_u_cost_R', 'low20_distance_R', 'r1_atr']
FEATURE_NAMES = ['cost_z', 'distance_z', 'r1_z', 'cost_missing', 'distance_missing',
    'r1_missing', 'external_missing', 's_z', 's_z*r1_z', 's_z*distance_z']
ARMS = ('COMMON_EVENT', 'INVENTORY', 'PAST_SHAM')
CUTOFFS = ('2020-01-01', '2023-01-01')
PARAMETERS = dict(alpha=1., fit_intercept=True, solver='cholesky')
IDENTITY = ['event_id', 'product_id', 'family_id', 'u_date', 'u_index']
LABEL_COLUMNS = IDENTITY + ['reference_epoch', 'entry_index', 'exit_index', 'entry_date',
    'exit_date', 'label_known_date', 'label_state', 'net_R_stress', 'label_history_ready20']


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


def write_csv(path, frame):
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    frame.to_csv(path, index=False, compression={'method': 'gzip', 'mtime': 0}, float_format='%.17g')
    return file_binding(path)


def training_slice(frame, cutoff):
    use = (frame.is_report_event.eq(1) & frame.u_date.lt(cutoff)
        & frame.label_known_date.ne('') & frame.label_known_date.lt(cutoff)
        & frame.label_state.eq('closed_complete_bar_model'))
    result = frame.loc[use].sort_values(['u_date', 'event_id']).copy()
    if len(result) and not np.isfinite(result.net_R_stress.to_numpy(float)).all():
        raise ValueError('mature target is not finite')
    return result


def training_weights(train):
    """Training-only family inclusive concurrency, report total1 then mean1."""
    if train.empty or train.report_id.eq('').any():
        raise ValueError('empty training or missing cohort')
    starts, ends = train.entry_index.to_numpy(float), train.exit_index.to_numpy(float)
    if (not np.isfinite(starts).all() or not np.isfinite(ends).all()
            or (starts < 0).any() or (ends < starts).any()
            or not np.equal(starts, starts.astype(np.int64)).all()
            or not np.equal(ends, ends.astype(np.int64)).all()):
        raise ValueError('invalid closed inclusive intervals')
    starts, ends = starts.astype(np.int64), ends.astype(np.int64)
    uniqueness = np.empty(len(train))
    families = train.family_id.to_numpy()
    for family in pd.unique(families):
        positions = np.flatnonzero(families == family)
        a, b = starts[positions], ends[positions]
        delta = np.zeros(int(b.max()) + 2, dtype=np.int64)
        np.add.at(delta, a, 1)
        np.add.at(delta, b + 1, -1)
        concurrency = np.cumsum(delta)[:-1]
        inverse = np.divide(1., concurrency, out=np.zeros(len(concurrency)), where=concurrency > 0)
        cumulative = np.r_[0., np.cumsum(inverse)]
        uniqueness[positions] = (cumulative[b + 1] - cumulative[a]) / (b - a + 1)
    totals = pd.Series(uniqueness).groupby(train.report_id.to_numpy()).transform('sum').to_numpy()
    report_weight = uniqueness / totals
    weights = report_weight / report_weight.mean()
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('nonpositive weights')
    return pd.DataFrame(dict(uniqueness=uniqueness, report_normalized_weight=report_weight,
        sample_weight=weights), index=train.index)


def _finite_stats(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    finite = np.isfinite(x)
    if not finite.any():
        return dict(mean=0., var=0., scale=1., finite_count=0)
    mean = float(np.average(x[finite], weights=w[finite]))
    var = float(np.average((x[finite] - mean) ** 2, weights=w[finite]))
    return dict(mean=mean, var=var, scale=math.sqrt(var) if var > 0 else 1., finite_count=int(finite.sum()))


def fit_scalers(train, weights):
    w = np.asarray(weights, float)
    if w.shape != (len(train),) or not len(w) or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError('invalid scaler weights')
    stats = [_finite_stats(train[c], w) for c in COMMON]
    observed = train.external_missing.eq(0).to_numpy()
    inventory, sham = train.inventory_s.to_numpy(float), train.past_sham_s.to_numpy(float)
    if not np.isfinite(inventory[observed]).all() or not np.isfinite(sham[observed]).all():
        raise ValueError('shared-observed scalar must be finite')
    q = _finite_stats(np.r_[np.where(observed, inventory, np.nan), np.where(observed, sham, np.nan)],
                      np.r_[w * .5, w * .5])
    return dict(common=dict(columns=COMMON, **{key: [s[key] for s in stats] for key in stats[0]}),
        q=q, feature_names=FEATURE_NAMES, n_features=10,
        weighting='same mature training rows; finite weighted population; two information arms half weight each',
        missing='common train mean imputation; shared external missing -> all new slots exact0',
        interaction_scaling='none beyond common and scalar standardization')


def design_matrix(frame, arm, scalers):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    raw = frame[COMMON].to_numpy(float)
    missing = ~np.isfinite(raw)
    means, scales = np.asarray(scalers['common']['mean']), np.asarray(scalers['common']['scale'])
    common = (np.where(missing, means, raw) - means) / scales
    external = frame.external_missing.to_numpy(dtype=np.int8)
    if not np.isin(external, [0, 1]).all():
        raise ValueError('invalid external missing state')
    q = np.zeros(len(frame))
    if arm != 'COMMON_EVENT':
        scalar = frame['inventory_s' if arm == 'INVENTORY' else 'past_sham_s'].to_numpy(float)
        observed = external == 0
        if not np.isfinite(scalar[observed]).all():
            raise ValueError('nonfinite observed scalar')
        q[observed] = (scalar[observed] - scalers['q']['mean']) / scalers['q']['scale']
    result = np.column_stack([common, missing.astype(float), external,
                              q, q * common[:, 2], q * common[:, 1]])
    if result.shape != (len(frame), 10) or not np.isfinite(result).all():
        raise ValueError('nonfinite or non10-slot design')
    return result


def prediction_frame(frame, scores, arm, cutoff):
    score = np.asarray(scores, float)
    if score.shape != (len(frame),) or not np.isfinite(score).all():
        raise ValueError('prediction scores must all be finite')
    result = frame[IDENTITY + ['is_report_event', 'report_id', 'external_missing']].copy()
    result['arm'], result['cutoff'], result['score'] = arm, cutoff, score
    result['history_ready20'] = frame.label_history_ready20.to_numpy(dtype=np.int8)
    result['selected'] = (result.is_report_event.eq(1) & result.history_ready20.eq(1) & result.score.gt(0)).astype(np.int8)
    return result


def join_events(labels, events):
    required = ['u_date', 'report_id', 'inventory_s', 'past_sham_s', 'external_missing']
    if events.u_date.duplicated().any() or events.report_id.duplicated().any():
        raise ValueError('event map is not unique by u/report')
    values = events[required].copy()
    if not values.external_missing.isin([0, 1]).all():
        raise ValueError('invalid external missing state')
    shared = values.external_missing.eq(1)
    if (not np.isfinite(values.loc[~shared, ['inventory_s', 'past_sham_s']].to_numpy(float)).all()
            or not values.loc[shared, ['inventory_s', 'past_sham_s']].eq(0).all().all()):
        raise ValueError('event scalar shared missing contract differs')
    result = labels.merge(values, how='left', on='u_date', validate='many_to_one', sort=False)
    result['is_report_event'] = result.report_id.notna().astype(np.int8)
    result['report_id'] = result.report_id.fillna('')
    result['external_missing'] = result.external_missing.fillna(1).astype(np.int8)
    for col in ('inventory_s', 'past_sham_s'):
        result[col] = result[col].fillna(0.)
    if len(result) != len(labels) or result.event_id.tolist() != labels.event_id.tolist():
        raise ValueError('full mother order changed by event join')
    return result


def validate_past_sham(features):
    if features.report_id.duplicated().any() or features.ordinal.duplicated().any():
        raise ValueError('duplicate report calendar identity')
    by_id = features.set_index('report_id')
    for row in features.itertuples():
        candidates = features.loc[(features.ordinal.lt(int(row.ordinal)))
            & features.ordinal.ge(int(row.ordinal) - 52)
            & np.isfinite(features.s.to_numpy(float))].sort_values('ordinal')
        shared_missing = not np.isfinite(float(row.s)) or candidates.empty
        if int(row.external_missing) != int(shared_missing):
            raise ValueError('past/shared missing state differs from known scalar history')
        if shared_missing:
            continue
        chosen = row.past_sham_report_id
        if chosen not in by_id.index:
            raise ValueError('past sham report missing')
        old = by_id.loc[chosen]
        if not (1 <= int(row.ordinal) - int(old.ordinal) <= 52) or not np.isfinite(float(old.s)):
            raise ValueError('past sham is not known inside prior52 calendar reports')
        code = int(hashlib.sha256(('stage057_past_sham_v1|' + row.report_id).encode()).hexdigest(), 16)
        expected_id = candidates.iloc[code % len(candidates)].report_id
        if chosen != expected_id:
            raise ValueError('past sham differs from frozen deterministic sample')
        if hasattr(row, 'past_sham_s') and float(row.past_sham_s) != float(old.s):
            raise ValueError('past sham value differs from selected known report')


def validate_event_map(events, features):
    """Keep exactly one retained report per u and preserve its shared payload."""
    retained = features.loc[features.u_date.notna()
        & features.superseded_before_first_decision.isin([False, 'False', 0])]
    if (events.report_id.duplicated().any() or events.u_date.duplicated().any()
            or set(events.report_id) != set(retained.report_id)):
        raise ValueError('event map report identities differ from retained calendar')
    expected = retained.set_index('report_id')
    for row in events.itertuples():
        report = expected.loc[row.report_id]
        if row.u_date != report.u_date or int(row.external_missing) != int(report.external_missing):
            raise ValueError('event map date/missing payload differs')
        if (float(row.inventory_s) != float(report.inventory_s)
                or float(row.past_sham_s) != float(report.past_sham_s)):
            raise ValueError('event map information scalar differs')


def make_estimator():
    return Ridge(**PARAMETERS)


def run_matrix(frame, output, *, estimator_factory=make_estimator, execution_kind='actual', counters=None):
    if execution_kind not in ('actual', 'synthetic_fixture'):
        raise ValueError('unknown execution kind')
    output = Path(output)
    counters = counters if counters is not None else dict(fit_calls_started=0, fit_calls_completed=0)
    predictions, fits = [], []
    with (output / 'fit_log.jsonl').open('x') as log:
        for i, cutoff in enumerate(CUTOFFS):
            next_cutoff = CUTOFFS[i + 1] if i + 1 < len(CUTOFFS) else None
            train = training_slice(frame, cutoff)
            use = frame.u_date.ge(cutoff)
            if next_cutoff:
                use &= frame.u_date.lt(next_cutoff)
            test = frame.loc[use].sort_values(['u_date', 'event_id']).copy()
            if train.empty or test.empty:
                raise ValueError('empty mature train or prediction block: ' + cutoff)
            weights = training_weights(train)
            scaler = fit_scalers(train, weights.sample_weight.to_numpy())
            for arm in ARMS:
                fit_id = cutoff[:4] + '_' + arm
                directory = output / 'fits' / fit_id
                directory.mkdir(parents=True, exist_ok=False)
                training = train[LABEL_COLUMNS + ['report_id']].copy()
                for col in weights:
                    training[col] = weights[col].to_numpy()
                weight_binding = write_csv(directory / 'training_weights.csv.gz', training)
                write_json(directory / 'scaler.json', scaler)
                x, xt = design_matrix(train, arm, scaler), design_matrix(test, arm, scaler)
                projection = directory / 'input_projection.npz'
                with projection.open('xb') as stream:
                    np.savez_compressed(stream, train_X=x, prediction_X=xt,
                        train_event_ids=train.event_id.to_numpy(dtype='U128'),
                        prediction_event_ids=test.event_id.to_numpy(dtype='U128'),
                        y=train.net_R_stress.to_numpy(float), sample_weight=weights.sample_weight.to_numpy())
                model = estimator_factory()
                counters['fit_calls_started'] += 1
                start = time.monotonic()
                log.write(json.dumps(dict(event='fit_started', fit_id=fit_id, **counters)) + '\n'); log.flush()
                print(f"fit {counters['fit_calls_started']}/6 START {fit_id} train={len(train)} test={len(test)}", flush=True)
                with threadpool_limits(limits=1):
                    model.fit(x, train.net_R_stress.to_numpy(float), sample_weight=weights.sample_weight.to_numpy())
                counters['fit_calls_completed'] += 1
                joblib.dump(model, directory / 'model.joblib', compress=3)
                portable = dict(schema='stage061_portable_ridge_v1', alpha=1., fit_intercept=True,
                    solver='cholesky', feature_names=FEATURE_NAMES, coef=np.asarray(model.coef_).tolist(),
                    intercept=float(model.intercept_), prediction_formula='X @ coef + intercept')
                write_json(directory / 'portable_model.json', portable)
                # Exact sufficient statistics allow independent normal-equation audit without another fit.
                w, y = weights.sample_weight.to_numpy(), train.net_R_stress.to_numpy(float)
                xm, ym = np.average(x, axis=0, weights=w), float(np.average(y, weights=w))
                xc, yc = x - xm, y - ym
                normal, rhs = xc.T @ (w[:, None] * xc) + np.eye(10), xc.T @ (w * yc)
                coef = np.asarray(model.coef_)
                write_json(directory / 'normal_equations.json', dict(weighted_X_mean=xm.tolist(),
                    weighted_y_mean=ym, centered_XtWX_plus_alphaI=normal.tolist(), centered_XtWy=rhs.tolist(),
                    coefficient_equation_max_abs_residual=float(np.max(np.abs(normal @ coef - rhs))),
                    intercept_equation_abs_residual=float(abs(model.intercept_ - (ym - xm @ coef)))))
                scores = model.predict(xt)
                if not np.allclose(scores, xt @ coef + model.intercept_, rtol=1e-12, atol=1e-12):
                    raise ValueError('portable Ridge prediction differs')
                predictions.append(prediction_frame(test, scores, arm, cutoff))
                record = dict(fit_id=fit_id, arm=arm, cutoff=cutoff, next_cutoff_exclusive=next_cutoff,
                    train_rows=len(train), prediction_rows=len(test), report_cohorts=int(train.report_id.nunique()),
                    training_families=sorted(train.family_id.unique()), max_u_date=str(train.u_date.max()),
                    max_label_known_date=str(train.label_known_date.max()), head_dimension=10,
                    training_weights=weight_binding, scaler=file_binding(directory / 'scaler.json'),
                    model=file_binding(directory / 'model.joblib'), portable_model=file_binding(directory / 'portable_model.json'),
                    normal_equations=file_binding(directory / 'normal_equations.json'), input_projection=file_binding(projection),
                    elapsed_seconds=time.monotonic() - start)
                write_json(directory / 'fit.json', record)
                fits.append(record)
                log.write(json.dumps(dict(event='fit_completed', fit_id=fit_id, **counters)) + '\n'); log.flush()
                print(f"fit {counters['fit_calls_completed']}/6 DONE {fit_id}", flush=True)
    combined = pd.concat(predictions, ignore_index=True).sort_values(['arm', 'u_date', 'event_id'])
    expected = set(frame.loc[frame.u_date.ge(CUTOFFS[0]), 'event_id'])
    if combined.duplicated(['event_id', 'arm']).any() or any(set(combined.loc[combined.arm.eq(a), 'event_id']) != expected for a in ARMS):
        raise ValueError('prediction mother coverage differs')
    binding = write_csv(output / 'predictions.csv.gz', combined)
    return dict(**counters, execution_kind=execution_kind,
        actual_fit_calls_started=counters['fit_calls_started'] if execution_kind == 'actual' else 0,
        actual_fit_calls_completed=counters['fit_calls_completed'] if execution_kind == 'actual' else 0,
        predictions=binding, fits=fits)


def load_protocol(path, sha):
    binding = file_binding(path)
    if binding['sha256'] != sha or sha != PROTOCOL_SHA:
        raise ValueError('frozen059 protocol SHA differs')
    protocol = json.loads(read_bound(binding))
    if (protocol['schema'] != 'stage059_eia_full_market_information_protocol_v1'
            or protocol['learner']['arms'] != list(ARMS) or protocol['learner']['cutoffs'] != list(CUTOFFS)
            or protocol['inputs']['design_order'] != FEATURE_NAMES
            or protocol['learner']['fit_calls_once'] != 6):
        raise ValueError('frozen059 experiment identity differs')
    read_bound(protocol['proposal'])
    return protocol, binding


def _csv(binding, **kwargs):
    return pd.read_csv(io.BytesIO(read_bound(binding)), compression='gzip' if binding['path'].endswith('.gz') else None, **kwargs)


def load_inputs(protocol, source_manifest, source_sha):
    source_binding = file_binding(source_manifest)
    if source_binding['sha256'] != source_sha:
        raise ValueError('060 source manifest SHA differs')
    source = json.loads(read_bound(source_binding))
    if source.get('schema') != 'stage060_eia_import_manifest_v1' or source.get('status') != 'completed':
        raise ValueError('060 actual import not complete')
    artifacts = source['artifacts']
    terminal = json.loads(read_bound(artifacts['actual_terminal']))
    if terminal.get('status') != 'completed':
        raise ValueError('060 actual terminal not complete')
    features = _csv(artifacts['report_features'], keep_default_na=False, na_values=[''])
    features['past_sham_report_id'] = features.past_sham_report_id.fillna('')
    validate_past_sham(features)
    events = _csv(artifacts['event_map'], keep_default_na=False, na_values=[''])
    validate_event_map(events, features)
    mother = protocol['inputs']['mother_labels']
    path = Path(mother['manifest'])
    if not path.is_absolute():
        path = LINE.parents[2] / path
    mother_binding = file_binding(path)
    if mother_binding['sha256'] != mother['sha256']:
        raise ValueError('accepted049 manifest SHA differs')
    manifest = json.loads(read_bound(mother_binding))
    label_binding = next(a for a in manifest['artifacts'] if a['role'] == 'economic_event_labels')
    labels = _csv(label_binding, usecols=LABEL_COLUMNS, dtype=str, keep_default_na=False)
    if len(labels) != 399252 or labels.event_id.duplicated().any():
        raise ValueError('accepted399252 mother differs')
    identity_binding = protocol['inputs']['prepared_common_identity']
    identity = json.loads(read_bound(identity_binding))
    if identity['rows'] != len(labels) or identity['event_ids_sha256'] != sha_bytes(('\n'.join(labels.event_id) + '\n').encode()):
        raise ValueError('prepared common original049 row identity differs')
    npz_binding = protocol['inputs']['prepared_common']
    raw = read_bound(npz_binding)
    with np.load(io.BytesIO(raw), allow_pickle=False) as prepared:
        columns = prepared['columns'].tolist()
        common = prepared['common']
        if columns != identity['columns'] or common.shape != (399252, len(columns)):
            raise ValueError('prepared common schema differs')
        for col in COMMON:
            labels[col] = common[:, columns.index(col)]
    for col in ('u_index', 'entry_index', 'exit_index', 'net_R_stress', 'label_history_ready20'):
        labels[col] = pd.to_numeric(labels[col].replace('', np.nan), errors='raise')
    labels['u_index'] = labels.u_index.astype(np.int32)
    if (not labels.label_history_ready20.isin([0, 1]).all()
            or not labels.family_id.eq(labels.product_id.str.removesuffix('_F')).all()
            or int(labels.u_date.ge('2020-01-01').sum()) != 161014):
        raise ValueError('mother ready/family/prediction domain differs')
    closed = labels.label_state.eq('closed_complete_bar_model')
    if int(closed.sum()) != 180507 or labels.loc[~closed, 'net_R_stress'].notna().any():
        raise ValueError('accepted049 closed/unknown target contract differs')
    if not labels.loc[closed, 'label_known_date'].gt(labels.loc[closed, 'u_date']).all():
        raise ValueError('invalid label maturity')
    frame = join_events(labels, events)
    inputs = dict(labels=label_binding, mother_manifest=mother_binding,
        prepared_common=npz_binding, prepared_common_identity=identity_binding,
        event_map=artifacts['event_map'], report_features=artifacts['report_features'])
    return frame, source_binding, inputs


def authorize(path, sha, protocol_binding, source_binding, source):
    auth_binding = file_binding(path)
    if auth_binding['sha256'] != sha:
        raise ValueError('authorization SHA differs')
    auth = json.loads(read_bound(auth_binding))
    expected = dict(kind='stage061_fit_once', protocol_sha256=protocol_binding['sha256'],
        source_import_manifest_sha256=source_binding['sha256'], source_sha256=source['sha256'], fit_calls=6)
    if any(auth.get(k) != v for k, v in expected.items()) or auth.get('authorized') is not True:
        raise ValueError('missing root-issued six-fit authorization')
    return auth_binding


def execute(args):
    protocol, protocol_binding = load_protocol(args.protocol, args.protocol_sha256)
    source = file_binding(__file__, 'experiment_source')
    tests = file_binding(Path(__file__).with_name('test_stage061_eia_event_fit.py'), 'new_behavior_tests')
    frame, source_binding, inputs = load_inputs(protocol, args.source_manifest, args.source_manifest_sha256)
    auth_binding = None
    if args.mode == 'actual':
        if not args.authorization or not args.authorization_sha256:
            raise ValueError('actual requires explicit root-issued authorization and SHA')
        auth_binding = authorize(args.authorization, args.authorization_sha256, protocol_binding, source_binding, source)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    counters = dict(fit_calls_started=0, fit_calls_completed=0)
    start, status, error, result = time.monotonic(), 'failed', None, {}
    write_json(out / ('actual_started.json' if args.mode == 'actual' else 'preflight_started.json'),
        dict(status='started', mode=args.mode, started_at_utc=datetime.now(timezone.utc).isoformat(),
             source=source, tests=tests, protocol=protocol_binding, source_import_manifest=source_binding,
             actual_fit_calls_started=0, actual_fit_calls_completed=0, native_source_queries=0,
             new_cash_accounts=0, authorization=auth_binding))
    try:
        write_json(out / 'input_bindings.json', dict(protocol=protocol_binding,
            source_import_manifest=source_binding, inputs=inputs, authorization=auth_binding,
            source=source, tests=tests, old009_targets_masks_models_read=False, native_SQL=0))
        write_csv(out / 'input_projection.csv.gz', frame[LABEL_COLUMNS + COMMON +
            ['is_report_event', 'report_id', 'inventory_s', 'past_sham_s', 'external_missing']])
        write_json(out / 'versions.json', dict(python=sys.version, platform=platform.platform(),
            sklearn=sklearn.__version__, numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__,
            joblib=joblib.__version__, estimator_parameters=make_estimator().get_params()))
        diagnostics = []
        for cutoff in CUTOFFS:
            train = training_slice(frame, cutoff)
            weights = training_weights(train)
            scaler = fit_scalers(train, weights.sample_weight.to_numpy())
            diagnostics.append(dict(cutoff=cutoff, train_rows=len(train),
                report_cohorts=int(train.report_id.nunique()), families=sorted(train.family_id.unique()),
                max_u_date=str(train.u_date.max()), max_label_known_date=str(train.label_known_date.max()), scaler=scaler))
        write_json(out / 'preflight.json', dict(mother_rows=len(frame), prediction_rows_per_arm=161014,
            report_event_rows=int(frame.is_report_event.sum()), cutoff_diagnostics=diagnostics,
            research_fit_calls=0, native_SQL=0, new_cash_accounts=0, ready_for_root_fit_authorization=True))
        if args.mode == 'actual':
            result = run_matrix(frame, out, counters=counters)
            if counters != dict(fit_calls_started=6, fit_calls_completed=6):
                raise ValueError('six-fit finite budget differs')
        if file_binding(__file__)['sha256'] != source['sha256'] or file_binding(tests['path'])['sha256'] != tests['sha256']:
            raise ValueError('source/test bytes drifted during execution')
        status = 'completed'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        terminal = dict(status=status, exit_code=0 if status == 'completed' else 1, mode=args.mode,
            actual_fit_calls_started=counters['fit_calls_started'], actual_fit_calls_completed=counters['fit_calls_completed'],
            native_source_queries=0, new_cash_accounts=0, source=source, tests=tests,
            elapsed_seconds=time.monotonic() - start, error=error,
            goal_complete=False, production_qualified=False, narrow_stop_or_increased_bet_qualified=False)
        write_json(out / ('actual_terminal.json' if args.mode == 'actual' else 'preflight_terminal.json'), terminal)
        terminal_path = out / ('actual_terminal.json' if args.mode == 'actual' else 'preflight_terminal.json')
        def role(p):
            if p.name == 'model.joblib': return 'model_artifact'
            if p.name == 'portable_model.json': return 'portable_model'
            if p.name == 'training_weights.csv.gz': return 'training_weights_and_intervals'
            if p.name == 'scaler.json': return 'training_scaler'
            if p.name == 'normal_equations.json': return 'normal_equation_audit'
            if 'projection' in p.name: return 'normalized_model_input_projection'
            if p.name == 'predictions.csv.gz': return 'full_mother_predictions'
            return 'qualification_evidence'
        artifacts = [file_binding(p, role(p)) for p in sorted(out.rglob('*')) if p.is_file()]
        write_json(out / 'manifest.json', dict(schema='stage061_eia_event_fit_v1', **{**terminal, **result},
            protocol=protocol_binding, source_import_manifest=source_binding, inputs=inputs,
            authorization=auth_binding, terminal=file_binding(terminal_path), artifacts=artifacts,
            prediction_rows_per_arm=161014, actual_research_run=args.mode == 'actual'))
    return dict(status=status, mode=args.mode, manifest=file_binding(out / 'manifest.json'), **counters)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['preflight', 'actual'], required=True)
    for flag in ('protocol', 'protocol-sha256', 'source-manifest', 'source-manifest-sha256', 'output'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--authorization')
    parser.add_argument('--authorization-sha256')
    args = parser.parse_args(argv)
    print(json.dumps(execute(args), ensure_ascii=False))


if __name__ == '__main__':
    main()
