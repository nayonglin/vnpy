from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage053_late_session_training'
OUTPUT = ROOT / 'artifacts' / STAGE
FEATURE_OUTPUT = ROOT / 'artifacts/stage052_late_session_features'
FEATURE_SHA = '3a8ebe7ed70010886707f73de9115775af61a3ef9c537e016bb731bda35e0b20'
SNAPSHOT = ROOT / 'artifacts/stage043_label_collection/20260907_051249_482153/summary.json'
SNAPSHOT_SHA = 'c4d00014ce724bb20645dfcb79eec6d2728ebbff70a2143d65f2cd0b89a3aacd'
CONTRACT = ROOT / 'stages/20260907_0726_stage053_late_session_training_contract.md'


def load(name):
    spec = importlib.util.spec_from_file_location('late_training053_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def join_features(data, features, base, spec):
    late = load('stage052_late_session_features')
    if spec != late.candidate_spec(base):
        raise RuntimeError('late_training_spec_changed')
    required = {*late.IDS, *late.FEATURES, 'asof_close', 'last_minute', 'late_minute_count', 'status'}
    forbidden = {'return_marginal', 'drawdown_marginal', 'label_status', 'label_end_date', *late.BASE_FEATURES}
    if (not required.issubset(features.columns) or forbidden.intersection(features.columns)
            or set(late.FEATURES).intersection(data.columns)
            or data.observation_id.isna().any() or data.observation_id.duplicated().any()
            or features.observation_id.isna().any() or features.observation_id.duplicated().any()
            or len(data) != len(features) or set(data.observation_id) != set(features.observation_id)):
        raise RuntimeError('late_training_inventory_invalid')
    ordered = features.set_index('observation_id').loc[data.observation_id].reset_index()
    if not ordered[list(late.IDS)].equals(data[list(late.IDS)].reset_index(drop=True)):
        raise RuntimeError('late_training_identity_mismatch')
    if (not ordered.status.eq('qualified').all() or not ordered.late_minute_count.eq(30).all()
            or not ordered.asof_close.eq(ordered.date + 'T15:00:00').all()
            or not ordered.last_minute.eq(ordered.date + 'T14:59:00').all()
            or not np.isfinite(ordered[list(late.FEATURES)].to_numpy(dtype=float)).all()
            or not (ordered.late_volume_fraction_30m.gt(0) & ordered.late_volume_fraction_30m.le(1)).all()):
        raise RuntimeError('late_training_source_not_qualified')
    result = data.copy(deep=True)
    for name in late.FEATURES:
        result[name] = ordered[name].to_numpy(copy=True)
    pd.testing.assert_frame_equal(result[data.columns], data, check_exact=True)
    return result


def load_dataset(snapshot, expected_sha256):
    if Path(snapshot).resolve() != SNAPSHOT or expected_sha256 != SNAPSHOT_SHA:
        raise RuntimeError('late_training_fixed_snapshot_required')
    identity = load('stage050_holding_failure_diagnostics')
    feature_sources = {}
    summary_path = FEATURE_OUTPUT / 'summary.json'
    identity.bind(summary_path, {'sha256': FEATURE_SHA}, feature_sources)
    summary = identity.read_json(summary_path)
    if (summary['status'] != 'features_qualified_no_models' or not summary['all_observations_qualified']
            or summary['observation_count'] != 1002 or summary['qualified_count'] != 1002
            or summary['failed_count'] != 0 or summary['feature_count'] != 11):
        raise RuntimeError('late_training_feature_campaign_incomplete')
    for name, expected in summary['outputs'].items():
        identity.bind(FEATURE_OUTPUT / name, expected, feature_sources)
    feature_manifest = identity.read_json(FEATURE_OUTPUT / 'input_manifest.json')
    for path, expected in feature_manifest['source_identities'].items():
        identity.bind(path, expected, feature_sources)
    parent = load('stage044_holding_training')
    data, base, months, dataset, paths, runner, manifest, bound = parent.load_verified_snapshot(snapshot, expected_sha256)
    spec = identity.read_json(FEATURE_OUTPUT / 'candidate_spec.json')
    features = pd.read_csv(FEATURE_OUTPUT / 'observation_late_features.csv', float_precision='round_trip')
    combined = join_features(data, features, base, spec)
    if len(combined) != 1002 or len(spec['features']) != 11:
        raise RuntimeError('late_training_dimensions_changed')
    for path, expected in feature_sources.items():
        if path in bound and bound[path] != expected:
            raise RuntimeError('late_training_source_identity_conflict')
    bound = {**bound, **feature_sources}
    paths.update(Path(path) for path in bound)
    paths.update({Path(__file__).resolve(), CONTRACT, ROOT / 'tests/test_stage053_late_session_training.py',
        ROOT / 'tools/stage044_holding_training.py', ROOT / 'tools/stage052_late_session_features.py'})
    dataset = {**dataset, 'late_feature_summary_sha256': FEATURE_SHA,
        'late_feature_table_sha256': summary['outputs']['observation_late_features.csv']['sha256'],
        'candidate_spec_sha256': summary['outputs']['candidate_spec.json']['sha256'],
        'combined_dataset_sha256': hashlib.sha256(combined.to_csv(index=False, float_format='%.17g').encode()).hexdigest()}
    return combined, spec, months, dataset, paths, runner, manifest, bound


def campaign():
    parent = load('stage044_holding_training')
    parent.OUTPUT, parent.CONTRACT = OUTPUT, CONTRACT
    parent.__file__ = str(Path(__file__).resolve())
    parent.load_verified_snapshot = load_dataset
    original_load = parent.load

    def adapted_load(name):
        module = original_load(name)
        if name == 'stage004_label_batch':
            original_write = module.write_json

            def write(path, payload):
                if Path(path) == OUTPUT / 'summary.json' and payload.get('stage') == 'stage044_holding_training':
                    payload = {**payload, 'stage': STAGE, 'parent_implementation': 'stage044_holding_training',
                        'late_feature_summary_sha256': FEATURE_SHA, 'feature_count': 11}
                return original_write(path, payload)

            module.write_json = write
        return module

    parent.load = adapted_load
    return parent


def run():
    if OUTPUT.exists():
        raise RuntimeError('late_training_campaign_already_exists')
    parent = campaign()
    parent.run_campaign(SNAPSHOT, SNAPSHOT_SHA)
    return json.loads((OUTPUT / 'summary.json').read_text())


if __name__ == '__main__':
    run()
