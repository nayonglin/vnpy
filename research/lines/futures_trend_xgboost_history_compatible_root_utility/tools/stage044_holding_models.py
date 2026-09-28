from __future__ import annotations

from collections import Counter
from datetime import date
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('holding044_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def digest(path):
    return load('stage006_monthly_models').digest(path)


def training_rows(data, cutoff, spec):
    import numpy as np
    import pandas as pd

    base = load('stage006_monthly_models')
    base.validate_cutoff(cutoff)
    identifiers = ('observation_id', 'root_id', 'product_vt_symbol', 'vt_symbol')
    required = {*identifiers, 'date', 'label_end_date', 'label_status', *spec['features'], *spec['targets']}
    if (not required.issubset(data.columns) or data.empty or data.observation_id.duplicated().any()
            or data.duplicated(['root_id', 'date']).any()
            or not data.label_status.eq('verified').all() or data.product_vt_symbol.eq('fu.SHFE').any()
            or any(not data[key].map(lambda v: isinstance(v, str) and bool(v)).all() for key in identifiers)):
        raise RuntimeError('holding_training_inventory_invalid')
    base.feature_matrix(data, spec)
    if not np.isfinite(data[spec['targets']].to_numpy(dtype=float)).all():
        raise RuntimeError('holding_training_target_nonfinite')
    for key in ('date', 'label_end_date'):
        values = data[key]
        if (not values.map(lambda v: isinstance(v, str)).all()
                or not values.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all()
                or pd.to_datetime(values, format='%Y-%m-%d', errors='coerce').isna().any()):
            raise RuntimeError('holding_training_date_invalid')
    if (data.label_end_date.le(data.date).any()
            or data.groupby('root_id')[['label_end_date', 'product_vt_symbol']].nunique().gt(1).any().any()):
        raise RuntimeError('holding_training_root_identity')
    jobs = [{'observation_id': r['observation_id'], 'root_id': r['root_id'], 'date': r['date'],
             'end_date': r['label_end_date'], 'status': 'mature'} for r in data.to_dict('records')]
    selected = load('stage040_holding_panel').training_selection(jobs, cutoff)
    train = data.set_index('observation_id', drop=False).loc[[key for key, _ in selected]].copy()
    train['sample_weight'] = [weight for _, weight in selected]
    return train.reset_index(drop=True)


def fit_month(data, cutoff, spec, estimator_factory=None):
    import numpy as np

    base = load('stage006_monthly_models')
    train = training_rows(data, cutoff, spec)
    columns = ['observation_id', 'root_id', 'date', 'label_end_date', *spec['features'], *spec['targets'], 'sample_weight']
    signature = hashlib.sha256(train[columns].to_csv(index=False, float_format='%.17g').encode()).hexdigest()
    bundle = {'cutoff': cutoff, 'status': 'untrained', 'train_count': len(train),
        'root_count': train.root_id.nunique(), 'train_observation_ids': train.observation_id.tolist(),
        'train_root_ids': train.root_id.tolist(), 'train_weights': train.sample_weight.tolist(),
        'train_frame_sha256': signature, 'spec_sha256': base.spec_digest(spec),
        'max_train_date': str(train.date.max()) if len(train) else None,
        'max_train_end': str(train.label_end_date.max()) if len(train) else None, 'heads': {}, 'fit_count': 0}
    if bundle['root_count'] < spec['minimum_mature_roots']:
        return bundle
    features = base.feature_matrix(train, spec)
    weights = train.sample_weight.to_numpy(dtype=float)
    for target in spec['targets']:
        values = train[target].to_numpy(dtype=float)
        constant = bool(np.all(values == values[0]))
        mean = float(values[0] if constant else np.average(values, weights=weights))
        std = 0.0 if constant else float(np.sqrt(np.average((values - mean) ** 2, weights=weights)))
        if not math.isfinite(mean) or not math.isfinite(std) or (not constant and std <= 0):
            raise RuntimeError('holding_target_transform_invalid')
        head = {'kind': 'constant' if constant else 'xgboost', 'mean': mean, 'std': std, 'estimator': None}
        if not constant:
            if estimator_factory is None:
                from xgboost import XGBRegressor
                estimator_factory = XGBRegressor
            head['estimator'] = estimator_factory(**spec['estimator'])
            head['estimator'].fit(features, (values - mean) / std, sample_weight=weights)
            bundle['fit_count'] += 1
        bundle['heads'][target] = head
    bundle['status'] = 'trained'
    return bundle


def validate_metadata(bundle, spec):
    base = load('stage006_monthly_models')
    base.validate_cutoff(bundle['cutoff'])
    observations, roots, weights = (bundle[key] for key in ('train_observation_ids', 'train_root_ids', 'train_weights'))
    counts = Counter(roots)
    if (bundle['spec_sha256'] != base.spec_digest(spec) or bundle['train_count'] != len(observations)
            or len(set(observations)) != len(observations) or len(roots) != len(observations)
            or len(weights) != len(observations) or bundle['root_count'] != len(counts)
            or any(not isinstance(v, str) or not v for v in [*observations, *roots])
            or any(weight != 1. / counts[root] for weight, root in zip(weights, roots))):
        raise RuntimeError('holding_model_training_identity_invalid')
    for key in ('max_train_date', 'max_train_end'):
        value = bundle[key]
        if not observations:
            if value is not None:
                raise RuntimeError('holding_model_empty_training_date')
        elif (not isinstance(value, str) or date.fromisoformat(value).isoformat() != value or value >= bundle['cutoff']):
            raise RuntimeError('holding_model_training_date_invalid')
    if observations and bundle['max_train_date'] >= bundle['max_train_end']:
        raise RuntimeError('holding_model_training_endpoint_invalid')
    trained = bundle['root_count'] >= spec['minimum_mature_roots']
    if (bundle['status'] != ('trained' if trained else 'untrained')
            or set(bundle['heads']) != (set(spec['targets']) if trained else set())):
        raise RuntimeError('holding_model_heads_invalid')
    fits = 0
    for head in bundle['heads'].values():
        if not math.isfinite(head['mean']) or not math.isfinite(head['std']):
            raise RuntimeError('holding_model_transform_invalid')
        if head['kind'] == 'xgboost' and head['std'] > 0:
            fits += 1
        elif head['kind'] != 'constant' or head['std'] != 0:
            raise RuntimeError('holding_model_head_invalid')
    if bundle['fit_count'] != fits:
        raise RuntimeError('holding_model_fit_count_invalid')


def save_bundle(bundle, root, spec):
    validate_metadata(bundle, spec)
    return load('stage006_monthly_models').save_bundle(bundle, root, spec)


def load_bundle(root, expected_metadata_sha256, spec):
    root = Path(root)
    path = root / 'metadata.json'
    if digest(path) != expected_metadata_sha256:
        raise RuntimeError('holding_model_metadata_changed')
    bundle = json.loads(path.read_text())
    validate_metadata(bundle, spec)
    for target, head in bundle['heads'].items():
        head['estimator'] = None
        if head['kind'] == 'xgboost':
            path = root / (target + '.ubj')
            if digest(path) != head['model_sha256']:
                raise RuntimeError('holding_model_file_changed')
            from xgboost import XGBRegressor
            model = XGBRegressor(n_jobs=spec['estimator']['n_jobs'])
            model.load_model(path)
            if model.get_booster().feature_names != spec['features']:
                raise RuntimeError('holding_model_feature_names_changed')
            head['estimator'] = model
    return bundle


def predict_decision(bundle, decision_date, product, current_features, spec):
    import pandas as pd

    parsed = date.fromisoformat(decision_date)
    if parsed.isoformat() != decision_date:
        raise RuntimeError('holding_decision_date_invalid')
    cutoff = parsed.replace(day=1).isoformat()
    result = {'cutoff': cutoff, 'status': 'untrained', 'exit': False,
              'return_marginal': None, 'drawdown_marginal': None}
    if product == 'fu.SHFE':
        return {**result, 'status': 'fixed_fu'}
    if bundle is None:
        raise RuntimeError('holding_decision_model_missing')
    if bundle['cutoff'] != cutoff:
        raise RuntimeError('holding_decision_model_month_mismatch')
    validate_metadata(bundle, spec)
    if bundle['status'] == 'untrained':
        return result
    if set(current_features) != set(spec['features']):
        raise RuntimeError('holding_current_feature_inventory')
    base = load('stage006_monthly_models')
    predictions = base.predict_bundle(bundle, pd.DataFrame([current_features]), spec)
    for target in spec['targets']:
        result[target] = float(predictions[target][0])
    result['status'] = 'predicted'
    result['exit'] = base.should_skip(result['return_marginal'], result['drawdown_marginal'], product)
    return result
