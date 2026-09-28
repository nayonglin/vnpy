from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/stage044_holding_training'
CONTRACT = ROOT / 'stages/20260906_1218_stage044_holding_training_contract.md'


def load(name):
    spec = importlib.util.spec_from_file_location('training044_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def check_versions(spec):
    return load('stage006_training_campaign').check_versions(spec)


def require_complete_summary(summary):
    expected = {'stage': 'stage043_label_collection', 'status': 'passed', 'verified': 1002, 'planned': 1002,
        'pending': 0, 'inherited_verified': 14, 'canonical_verified': 988, 'fully_verified_roots': 155,
        'roots_with_any_verified_observation': 155, 'total_observed_mature_roots': 155,
        'original_root_inventory': 276, 'unobserved_censored_roots_preserved_in_plan': 2,
        'unresolved_current_job_ids': []}
    if summary.get('training_ready') is not True or any(summary.get(k) != v for k, v in expected.items()):
        raise RuntimeError('holding_training_snapshot_incomplete')


def reconcile_snapshot_rows(data, jobs, features, labels, inherited):
    import pandas as pd

    expected, ready = load('stage043_label_collection').assemble(jobs, features, labels, inherited)
    if not ready:
        raise RuntimeError('holding_training_labels_incomplete')
    pd.testing.assert_frame_equal(data, expected, check_exact=True, check_dtype=False)


def load_verified_snapshot(snapshot, expected_sha256):
    import pandas as pd

    models = load('stage044_holding_models')
    snapshot = Path(snapshot).resolve(strict=True)
    snapshot.relative_to(ROOT / 'artifacts/stage043_label_collection')
    raw = snapshot.read_bytes()
    if snapshot.name != 'summary.json' or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('holding_training_snapshot_changed')
    summary = json.loads(raw)
    require_complete_summary(summary)
    current = load('stage042_holding_labels'); module = current.adapted(); _, runner = module.configured()
    snapshot_identity = runner._file_identity(snapshot)
    if snapshot_identity['size'] != len(raw) or snapshot_identity['sha256'] != expected_sha256:
        raise RuntimeError('holding_training_snapshot_changed')
    manifest_path = current.OUTPUT / 'input_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    runner.validate_frozen_input_contract(current.FREEZE, manifest)
    runner.validate_current_input_manifest(manifest); module.verify_panel(runner)
    if summary['file_contract_sha256'] != manifest['file_contract_sha256']:
        raise RuntimeError('holding_training_label_contract_changed')
    sources = summary['source_identities']
    for name, identity in sources.items():
        if runner._file_identity(Path(name)) != identity:
            raise RuntimeError('holding_training_snapshot_source_changed')
    if set(summary['outputs']) != {'observations.csv', 'counterfactual_metrics.csv'}:
        raise RuntimeError('holding_training_snapshot_outputs_invalid')
    for name, identity in summary['outputs'].items():
        if runner._file_identity(snapshot.parent / name) != identity:
            raise RuntimeError('holding_training_snapshot_output_changed')
    required = {current.FREEZE, manifest_path, current.SNAPSHOT / 'summary.json',
        current.LEGACY / 'input_manifest.json', ROOT / 'stages/stage041b_input_freeze.json'}
    required.update(module.PANEL / name for name in ('summary.json', 'jobs.json', 'features.csv', 'model_spec.json', 'monthly_inventory.json'))
    plan = module.read_plan(); jobs = plan['jobs']; inherited = current.inherited_ids()
    if (len(jobs) != 1002 or len({j['root_id'] for j in jobs}) != 155 or len(plan['roots']) != 276
            or sum(r['status'].startswith('right_censored') for r in plan['roots']) != 2):
        raise RuntimeError('holding_training_plan_inventory_changed')
    if {p.name for p in (current.OUTPUT / 'jobs').iterdir()} != {j['observation_id'] for j in jobs} - inherited:
        raise RuntimeError('holding_training_current_job_inventory_changed')
    labels = {}
    for job in jobs:
        identifier = job['observation_id']; owner = current.LEGACY if identifier in inherited else current.OUTPUT
        root = owner / 'jobs' / identifier
        for name in ('label.json', 'receipt.json', 'archive_receipt.json', 'exit_audit.json'):
            required.add(root / name)
        labels[identifier] = json.loads((root / 'label.json').read_text())
    if not {str(p) for p in required}.issubset(sources):
        raise RuntimeError('holding_training_snapshot_missing_source_binding')
    features = pd.read_csv(module.PANEL / 'features.csv', float_precision='round_trip')
    data = pd.read_csv(snapshot.parent / 'observations.csv', float_precision='round_trip')
    reconcile_snapshot_rows(data, jobs, features, labels, inherited)
    spec = json.loads((module.PANEL / 'model_spec.json').read_text())
    months = json.loads((module.PANEL / 'monthly_inventory.json').read_text())
    expected_months = [v.strftime('%Y-%m-01') for v in pd.period_range('2020-01', '2026-08', freq='M')]
    if [v['cutoff'] for v in months] != expected_months:
        raise RuntimeError('holding_training_month_inventory_changed')
    bound = {**sources, **{v['path']: v for v in summary['outputs'].values()},
        str(snapshot): snapshot_identity}
    if any(runner._file_identity(Path(path)) != identity for path, identity in bound.items()):
        raise RuntimeError('holding_training_source_drift')
    paths = {Path(p) for p in bound}
    identities = {'snapshot_sha256': expected_sha256, 'dataset_sha256': models.digest(snapshot.parent / 'observations.csv'),
        'model_spec_sha256': models.digest(module.PANEL / 'model_spec.json'), 'file_contract_sha256': manifest['file_contract_sha256']}
    return data, spec, months, identities, paths, runner, manifest, bound


def fit_schedule(data, spec, months, output):
    import pandas as pd

    models = load('stage044_holding_models'); batch = load('stage004_label_batch')
    cutoffs = [month['cutoff'] for month in months]
    if not cutoffs or cutoffs != sorted(set(cutoffs)):
        raise RuntimeError('holding_training_month_order_invalid')
    # Check the entire frozen schedule before the first historical fit or write.
    for month in months:
        train = models.training_rows(data, month['cutoff'], spec)
        weights = [[key, weight] for key, weight in zip(train.observation_id, train.sample_weight)]
        if (month['mature_roots'] != train.root_id.nunique() or month['observation_count'] != len(train)
                or month['minimum_roots_met'] != (train.root_id.nunique() >= spec['minimum_mature_roots'])
                or month['weights'] != weights):
            raise RuntimeError('holding_training_month_plan_mismatch')
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    index, predictions = {}, []
    for cutoff in cutoffs:
        batch.write_json(output / f'started_{cutoff}.json', {'cutoff': cutoff, 'status': 'fit_not_yet_called'})
        bundle = models.fit_month(data, cutoff, spec)
        root = output / 'models' / cutoff
        sha = models.save_bundle(bundle, root, spec)
        restored = models.load_bundle(root, sha, spec)
        for row in data.loc[data.date.str[:7].eq(cutoff[:7])].to_dict('records'):
            features = {key: row[key] for key in spec['features']}
            before = models.predict_decision(bundle, row['date'], row['product_vt_symbol'], features, spec)
            after = models.predict_decision(restored, row['date'], row['product_vt_symbol'], features, spec)
            if before != after:
                raise RuntimeError('holding_saved_prediction_changed')
            predictions.append({key: row[key] for key in ('observation_id', 'root_id', 'date', 'product_vt_symbol', 'vt_symbol')} | after)
        index[cutoff] = {'metadata_sha256': sha, 'status': bundle['status'], 'root_count': bundle['root_count'],
            'train_count': bundle['train_count'], 'fit_count': bundle['fit_count'], 'train_frame_sha256': bundle['train_frame_sha256']}
        print(json.dumps({'cutoff': cutoff, **index[cutoff]}), flush=True)
    frame = pd.DataFrame(predictions)
    if (len(frame) != len(data) or frame.observation_id.duplicated().any()
            or set(frame.observation_id) != set(data.observation_id)):
        raise RuntimeError('holding_prediction_inventory_mismatch')
    return index, frame


def run_campaign(snapshot, expected_sha256):
    data, spec, months, dataset, paths, runner, manifest, bound = load_verified_snapshot(snapshot, expected_sha256)
    versions = check_versions(spec)
    if OUTPUT.exists():
        raise RuntimeError('holding_training_campaign_already_exists')
    models = load('stage044_holding_models'); batch = load('stage004_label_batch')
    import xgboost

    paths.update({Path(__file__).resolve(), Path(models.__file__), CONTRACT,
        ROOT / 'tests/test_stage044_holding_models.py', ROOT / 'tests/test_stage044_holding_training.py',
        ROOT / 'tests/test_stage048_training_snapshot_identity.py',
        ROOT / 'stages/20260906_1654_stage048_training_snapshot_identity_contract.md',
        ROOT / 'tools/stage006_monthly_models.py', ROOT / 'tools/stage006_training_campaign.py',
        ROOT / 'tools/stage004_label_batch.py', Path(xgboost.sklearn.__file__), Path(xgboost.core.__file__),
        Path(xgboost.core._LIB._name)})
    sources = {str(path): runner._file_identity(path) for path in sorted(paths)}
    if any(sources.get(path) != identity for path, identity in bound.items()):
        raise RuntimeError('holding_training_source_drift')
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'stage': 'stage044_holding_training'}, stream)
    try:
        runner.validate_current_input_manifest(manifest)
        if any(runner._file_identity(Path(path)) != identity for path, identity in sources.items()):
            raise RuntimeError('holding_training_source_drift')
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / 'input_manifest.json', {'source_identities': sources, 'dataset_identity': dataset,
            'versions': versions, 'spec': spec, 'months': months, 'evidence': spec['evidence']})
        network = runner.load_metadata_preflight_module().load_preflight_module().NetworkBlock()
        with network:
            index, predictions = fit_schedule(data, spec, months, OUTPUT)
        if network.attempts:
            raise RuntimeError('holding_training_network_attempt')
        runner.validate_current_input_manifest(manifest)
        if any(runner._file_identity(Path(path)) != identity for path, identity in sources.items()):
            raise RuntimeError('holding_training_source_drift')
        batch.write_json(OUTPUT / 'model_index.json', index)
        with (OUTPUT / 'baseline_observation_predictions.csv').open('x') as stream:
            predictions.to_csv(stream, index=False, float_format='%.17g')
        summary = {'stage': 'stage044_holding_training', 'status': 'passed', 'month_count': len(index),
            'trained_month_count': sum(v['status'] == 'trained' for v in index.values()),
            'historical_model_fit_count': sum(v['fit_count'] for v in index.values()),
            'baseline_observation_count': len(predictions), 'baseline_predicted_exit_count': int(predictions['exit'].sum()),
            'saved_prediction_mismatch_count': 0, 'new_strategy_replay_count': 0,
            'network_attempt_count': network.attempts, 'reviewer_count': 0, 'evidence': spec['evidence'],
            'output_identities': {name: runner._file_identity(OUTPUT / name) for name in
                ('input_manifest.json', 'model_index.json', 'baseline_observation_predictions.csv')}}
        batch.write_json(OUTPUT / 'summary.json', summary)
        print(json.dumps(summary), flush=True)
        return summary
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / 'failure.json').exists():
            batch.write_json(OUTPUT / 'failure.json', {'status': 'failed', 'error': str(exc),
                'historical_fit_attempts_may_have_occurred': True, 'traceback': traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--snapshot-sha256', required=True)
    args = parser.parse_args()
    run_campaign(args.snapshot, args.snapshot_sha256)


if __name__ == '__main__':
    main()
