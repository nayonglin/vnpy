from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('catalog045_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def checked_json(path, expected_sha256):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('holding_catalog_file_changed')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('holding_catalog_file_changed')
    return json.loads(raw)


def verify_predictions(path, jobs, index, summary):
    expected = {job['observation_id']: job for job in jobs}
    seen, exits = set(), 0
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields = {'observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol',
            'cutoff', 'status', 'exit', 'return_marginal', 'drawdown_marginal'}
        if set(reader.fieldnames or []) != fields or len(reader.fieldnames) != len(fields):
            raise RuntimeError('holding_catalog_prediction_columns')
        for row in reader:
            identifier = row['observation_id']
            job = expected.get(identifier)
            if job is None or identifier in seen or any(row[key] != job[key] for key in
                    ('root_id', 'date', 'product_vt_symbol', 'vt_symbol')):
                raise RuntimeError('holding_catalog_prediction_identity')
            seen.add(identifier)
            cutoff = job['date'][:7] + '-01'
            status = 'predicted' if index[cutoff]['status'] == 'trained' else 'untrained'
            if row['cutoff'] != cutoff or row['status'] != status or row['exit'] not in {'True', 'False'}:
                raise RuntimeError('holding_catalog_prediction_month')
            if status == 'untrained':
                if row['return_marginal'] or row['drawdown_marginal'] or row['exit'] != 'False':
                    raise RuntimeError('holding_catalog_untrained_prediction')
            else:
                values = [float(row[key]) for key in ('return_marginal', 'drawdown_marginal')]
                if not all(math.isfinite(value) for value in values):
                    raise RuntimeError('holding_catalog_prediction_nonfinite')
                if (row['exit'] == 'True') != all(value < 0 for value in values):
                    raise RuntimeError('holding_catalog_prediction_action')
            exits += row['exit'] == 'True'
    if seen != set(expected) or exits != summary['baseline_predicted_exit_count']:
        raise RuntimeError('holding_catalog_prediction_inventory')


def load_catalog(root, expected_spec, expected_summary_sha256, expected_jobs, expected_months):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or (root / 'failure.json').exists():
        raise RuntimeError('holding_training_campaign_not_complete')
    root = root.resolve()
    summary_path = root / 'summary.json'
    summary = checked_json(summary_path, expected_summary_sha256)
    required = {'stage': 'stage044_holding_training', 'status': 'passed', 'baseline_observation_count': 1002,
        'saved_prediction_mismatch_count': 0, 'network_attempt_count': 0, 'new_strategy_replay_count': 0,
        'reviewer_count': 0, 'evidence': expected_spec['evidence']}
    if any(summary.get(key) != value for key, value in required.items()):
        raise RuntimeError('holding_catalog_summary_invalid')
    outputs = {'input_manifest.json', 'model_index.json', 'baseline_observation_predictions.csv'}
    if set(summary['output_identities']) != outputs:
        raise RuntimeError('holding_catalog_output_inventory')
    base = load('stage008_model_catalog')
    models = load('stage044_holding_models')
    panel = load('stage040_holding_panel')
    files = [summary_path]
    for name, identity in summary['output_identities'].items():
        base.verify_file(root / name, identity)
        files.append(root / name)
    manifest = checked_json(root / 'input_manifest.json', summary['output_identities']['input_manifest.json']['sha256'])
    if (manifest['spec'] != expected_spec or manifest['versions'] != expected_spec['versions']
            or manifest['evidence'] != expected_spec['evidence'] or manifest['months'] != expected_months):
        raise RuntimeError('holding_catalog_spec_or_plan_changed')
    dataset = manifest['dataset_identity']
    if (set(dataset) != {'snapshot_sha256', 'dataset_sha256', 'model_spec_sha256', 'file_contract_sha256'}
            or any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value) for value in dataset.values())
            or not manifest['source_identities']):
        raise RuntimeError('holding_catalog_dataset_identity')
    for source, identity in manifest['source_identities'].items():
        base.verify_file(source, identity)
        files.append(Path(source))
    months = [f'{year}-{month:02}-01' for year in range(2020, 2027)
              for month in range(1, 13) if (year, month) <= (2026, 8)]
    jobs = {job['observation_id']: job for job in expected_jobs}
    if (len(expected_jobs) != 1002 or len(jobs) != 1002 or len({job['root_id'] for job in expected_jobs}) != 155
            or [month['cutoff'] for month in expected_months] != months):
        raise RuntimeError('holding_catalog_expected_inventory')
    for job in expected_jobs:
        if (job['status'] != 'mature' or job['product_vt_symbol'] == 'fu.SHFE'
                or any(date.fromisoformat(job[key]).isoformat() != job[key] for key in ('date', 'end_date'))
                or job['date'][:7] + '-01' not in months):
            raise RuntimeError('holding_catalog_expected_job')
    index = checked_json(root / 'model_index.json', summary['output_identities']['model_index.json']['sha256'])
    if (set(index) != set(months) or summary['month_count'] != len(months)
            or summary['trained_month_count'] != sum(row['status'] == 'trained' for row in index.values())
            or summary['historical_model_fit_count'] != sum(row['fit_count'] for row in index.values())
            or (root / 'models').is_symlink()):
        raise RuntimeError('holding_catalog_month_inventory')
    registry, native_count = {}, 0
    for month in expected_months:
        cutoff = month['cutoff']; entry = index[cutoff]
        directory = root / 'models' / cutoff
        if directory.is_symlink():
            raise RuntimeError('holding_catalog_model_directory_changed')
        path = directory / 'metadata.json'
        meta = checked_json(path, entry['metadata_sha256'])
        models.validate_metadata(meta, expected_spec)
        selected = panel.training_selection(expected_jobs, cutoff)
        identifiers = [key for key, _ in selected]
        roots = [jobs[key]['root_id'] for key in identifiers]
        weights = [weight for _, weight in selected]
        if (month['mature_roots'] != len(set(roots)) or month['observation_count'] != len(selected)
                or month['minimum_roots_met'] != (len(set(roots)) >= expected_spec['minimum_mature_roots'])
                or month['weights'] != [[key, weight] for key, weight in selected]
                or meta['cutoff'] != cutoff or meta['train_observation_ids'] != identifiers
                or meta['train_root_ids'] != roots or meta['train_weights'] != weights
                or meta['max_train_date'] != max((jobs[key]['date'] for key in identifiers), default=None)
                or meta['max_train_end'] != max((jobs[key]['end_date'] for key in identifiers), default=None)
                or any(meta[key] != entry[key] for key in ('status', 'train_count', 'root_count', 'fit_count', 'train_frame_sha256'))):
            raise RuntimeError('holding_catalog_training_identity')
        files.append(path)
        for target, head in meta['heads'].items():
            if head['kind'] == 'xgboost':
                native = directory / (target + '.ubj')
                if native.is_symlink() or not native.is_file() or base.digest(native) != head['model_sha256']:
                    raise RuntimeError('holding_catalog_native_model_changed')
                files.append(native); native_count += 1
        registry[cutoff] = {'root': directory, 'metadata_sha256': entry['metadata_sha256']}
    if native_count != summary['historical_model_fit_count']:
        raise RuntimeError('holding_catalog_native_inventory')
    verify_predictions(root / 'baseline_observation_predictions.csv', expected_jobs, index, summary)
    return registry, expected_spec, {'summary_sha256': expected_summary_sha256, 'metadata_count': len(registry),
        'model_file_count': native_count, 'files': sorted(set(files)), 'dataset_identity': dataset}
