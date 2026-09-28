from __future__ import annotations

import copy
import importlib.util
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MODEL_OUTPUT = ROOT / 'artifacts/stage060_semivariance_training'
SUMMARY_SHA = 'f8a8ba69f9c2a024c076db3ede01e081fd5f4c0126c25eeaf1a7e3db47705262'
BASE_FEATURES = ('directional_unrealized_return', 'directional_day_return', 'day_range_fraction',
    'directional_close_location', 'log_holding_bars', 'layer_stop_buffer', 'portfolio_drawdown',
    'margin_to_equity', 'loss_streak')
EXTRA_FEATURES = ('favorable_semivariance_5m', 'adverse_semivariance_5m')
BASE_DATASET_KEYS = ('snapshot_sha256', 'dataset_sha256', 'model_spec_sha256', 'file_contract_sha256')
EXTRA_DATASET_KEYS = ('semivariance_feature_summary_sha256', 'semivariance_feature_table_sha256',
    'candidate_spec_sha256', 'combined_dataset_sha256')


def load(name):
    spec = importlib.util.spec_from_file_location('semivariance061_' + name, ROOT / 'tools' / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def load_catalog(root, expected_spec, expected_summary_sha256, expected_jobs, expected_months):
    parent = load('stage045_holding_catalog'); checked = parent.checked_json
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or (root / 'failure.json').exists():
        raise RuntimeError('semivariance_training_campaign_not_complete')
    root = root.resolve(); summary_path = root / 'summary.json'; manifest_path = root / 'input_manifest.json'
    summary = checked(summary_path, expected_summary_sha256)
    if (summary.get('stage') != 'stage060_semivariance_training' or summary.get('feature_count') != 11
            or summary.get('parent_implementation') != 'stage044_holding_training'
            or expected_spec.get('features') != [*BASE_FEATURES, *EXTRA_FEATURES]):
        raise RuntimeError('semivariance_catalog_stage_or_features_changed')
    manifest = checked(manifest_path, summary['output_identities']['input_manifest.json']['sha256'])
    dataset = manifest['dataset_identity']; sources = manifest['source_identities']
    if (set(dataset) != {*BASE_DATASET_KEYS, *EXTRA_DATASET_KEYS}
            or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in dataset.values())
            or dataset['semivariance_feature_summary_sha256'] != summary.get('semivariance_feature_summary_sha256')):
        raise RuntimeError('semivariance_catalog_dataset_identity')

    def bound(digest, decode=True):
        matches = [Path(path) for path, identity in sources.items() if identity['sha256'] == digest]
        if not matches:
            raise RuntimeError('semivariance_catalog_source_identity_missing')
        values = [checked(path, digest) for path in matches] if decode else []
        if values and any(value != values[0] for value in values):
            raise RuntimeError('semivariance_catalog_source_identity_conflict')
        return values[0] if values else None

    base = copy.deepcopy(expected_spec); base['features'] = list(BASE_FEATURES)
    if bound(dataset['model_spec_sha256']) != base or bound(dataset['candidate_spec_sha256']) != expected_spec:
        raise RuntimeError('semivariance_catalog_candidate_spec_changed')
    feature_summary = bound(dataset['semivariance_feature_summary_sha256'])
    required = {'stage': 'stage059_realized_semivariance_features', 'status': 'features_qualified_no_models',
        'all_observations_qualified': True, 'observation_count': 1002, 'qualified_count': 1002,
        'failed_count': 0, 'feature_count': 11}
    if (any(feature_summary.get(k) != v for k, v in required.items())
            or feature_summary['outputs']['candidate_spec.json']['sha256'] != dataset['candidate_spec_sha256']
            or feature_summary['outputs']['observation_semivariance_features.csv']['sha256'] != dataset['semivariance_feature_table_sha256']):
        raise RuntimeError('semivariance_catalog_feature_source_invalid')
    bound(dataset['semivariance_feature_table_sha256'], decode=False)

    # Project schema only; all original source, temporal, root-weight and native-file gates still run.
    def projected_json(path, digest):
        value = checked(path, digest)
        if path == summary_path:
            value = {**value, 'stage': 'stage044_holding_training'}
        elif path == manifest_path:
            value = {**value, 'dataset_identity': {k: value['dataset_identity'][k] for k in BASE_DATASET_KEYS}}
        return value

    parent.checked_json = projected_json
    registry, spec, evidence = parent.load_catalog(root, expected_spec, expected_summary_sha256, expected_jobs, expected_months)
    return registry, spec, {**evidence, 'dataset_identity': dataset, 'feature_count': 11,
        'stage': 'stage060_semivariance_training'}


def holding_guard_class(preflight, baseline):
    parent = load('stage045_holding_inference').holding_guard_class(preflight, baseline)
    forbidden = {ROOT / 'artifacts' / path for path in (
        'stage059_realized_semivariance_features/observation_semivariance_features.csv',
        'stage059_realized_semivariance_features/sampled_prices.csv',
        'stage060_semivariance_training/baseline_observation_predictions.csv',
        'stage052_late_session_features/observation_late_features.csv',
        'stage053_late_session_training/baseline_observation_predictions.csv')}

    class SemivarianceInferenceGuard(parent):
        def _check_open(self, file, mode):
            path = self._resolve_path(file)
            if path in forbidden and not any(token in str(mode) for token in ('w', 'a', 'x', '+')):
                self._block('label_value_read_count', 'semivariance_A_table_read_forbidden')
            super()._check_open(file, mode)

        def predict_event(self, event):
            values = {k: v for k, v in event.items() if k not in {'decision_date', 'product_vt_symbol'}}
            if (self.spec.get('features') != [*BASE_FEATURES, *EXTRA_FEATURES]
                    or set(values) != set(self.spec['features'])
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                           for v in values.values())
                    or any(values[key] < 0 for key in EXTRA_FEATURES)):
                raise RuntimeError('semivariance_current_feature_domain')
            return super().predict_event(event)

    return SemivarianceInferenceGuard
