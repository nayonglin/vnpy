from __future__ import annotations

from collections import Counter
from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'stages/20260906_1126_stage041c_label_collection_contract.md'


def load(name):
    spec = importlib.util.spec_from_file_location('collection041c_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def label_rows(jobs, labels):
    ids = [job['observation_id'] for job in jobs]
    if len(ids) != len(set(ids)) or not set(labels).issubset(ids):
        raise ValueError('holding_collection_identity')
    rows = []
    for job in jobs:
        identifier = job['observation_id']; label = labels.get(identifier)
        row = {'observation_id': identifier, 'root_id': job['root_id'], 'label_end_date': job['end_date'],
               'label_status': 'pending', 'return_marginal': None, 'drawdown_marginal': None}
        if label is not None:
            if (label['status'] != 'passed' or any(label[key] != job[key] for key in
                    ('observation_id', 'root_id', 'date', 'end_date'))):
                raise ValueError('holding_collection_label_identity')
            for target in ('return_marginal', 'drawdown_marginal'):
                value = label['marginal'][target]
                if not isinstance(value, (float, int)) or not math.isfinite(value):
                    raise ValueError('holding_collection_nonfinite_target')
                row[target] = value
            row['label_status'] = 'verified'
        rows.append(row)
    return rows, set(labels) == set(ids)


def main():
    import pandas as pd

    batch = load('stage004_label_batch'); module = load('stage041b_numeric_inventory_labels').adapted()
    _, runner = module.configured()
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'mode': 'stage041c_label_collection'}, stream)
    try:
        manifest = json.loads((module.OUTPUT / 'input_manifest.json').read_text())
        runner.validate_frozen_input_contract(module.FREEZE, manifest)
        runner.validate_current_input_manifest(manifest); module.verify_panel(runner)
        plan = module.read_plan(); jobs = plan['jobs']
        expected = load('stage007a_runtime_equivalence').expected_frames('A0', manifest['formal_identity'])
        sources = [Path(__file__).resolve(), ROOT / 'tests/test_stage041c_label_collection.py', CONTRACT,
                   module.FREEZE, module.OUTPUT / 'input_manifest.json', module.PANEL / 'summary.json']
        sources.extend(module.PANEL / name for name in ('features.csv', 'jobs.json', 'model_spec.json', 'monthly_inventory.json'))
        identities = {str(path): runner._file_identity(path) for path in sources}
        labels, metrics, unfinished = {}, [], []
        allowed = {job['observation_id'] for job in jobs}
        if {path.name for path in (module.OUTPUT / 'jobs').iterdir()} - allowed:
            raise ValueError('holding_collection_unknown_job')
        for job in jobs:
            root = module.OUTPUT / 'jobs' / job['observation_id']
            path = root / 'label.json'
            if not path.exists():
                if root.exists():
                    unfinished.append(job['observation_id'])
                continue
            local_paths = [root / name for name in ('label.json', 'receipt.json', 'archive_receipt.json', 'exit_audit.json')]
            local_identities = {str(path): runner._file_identity(path) for path in local_paths}
            label = json.loads(path.read_text())
            if label != module.validate_job(job, root, manifest, expected, archived=True):
                raise ValueError('holding_collection_recomputed_label_mismatch')
            for name, identity in local_identities.items():
                if runner._file_identity(Path(name)) != identity:
                    raise ValueError('holding_collection_job_drift')
            identities.update(local_identities)
            labels[job['observation_id']] = label
            metrics.append({key: job[key] for key in ('observation_id', 'root_id', 'date', 'end_date', 'vt_symbol', 'direction')}
                           | {f'{arm}_{key}': value for arm in ('A', 'E') for key, value in label[arm + '_metrics'].items()})
        rows, ready = label_rows(jobs, labels)
        features = pd.read_csv(module.PANEL / 'features.csv', float_precision='round_trip')
        if set(features.observation_id) != allowed or features.observation_id.duplicated().any():
            raise ValueError('holding_collection_feature_inventory')
        dataset = features.merge(pd.DataFrame(rows), on='observation_id', validate='one_to_one')
        expected_counts = Counter(job['root_id'] for job in jobs)
        completed_counts = Counter(label['root_id'] for label in labels.values())
        runner.validate_current_input_manifest(manifest)
        for name, identity in identities.items():
            if runner._file_identity(Path(name)) != identity:
                raise ValueError('holding_collection_source_drift')
        output = ROOT / 'artifacts/stage041c_label_collection' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        output.mkdir(parents=True, exist_ok=False)
        with (output / 'observations.csv').open('x') as stream:
            dataset.to_csv(stream, index=False, float_format='%.17g')
        with (output / 'counterfactual_metrics.csv').open('x') as stream:
            pd.DataFrame(metrics).to_csv(stream, index=False, float_format='%.17g')
        result = {'stage': 'stage041c_label_collection', 'status': 'passed', 'verified': len(labels), 'planned': len(jobs),
            'pending': len(jobs) - len(labels), 'fully_verified_roots': sum(completed_counts[k] == n for k, n in expected_counts.items()),
            'roots_with_any_verified_observation': len(completed_counts), 'total_observed_mature_roots': len(expected_counts),
            'original_root_inventory': len(plan['roots']), 'unobserved_censored_roots_preserved_in_plan':
                sum(root['status'].startswith('right_censored') for root in plan['roots']),
            'unfinished_jobs': unfinished, 'training_ready': ready and not unfinished,
            'source_identities': identities, 'outputs': {name: runner._file_identity(output / name)
                for name in ('observations.csv', 'counterfactual_metrics.csv')},
            'new_replay_count': 0, 'historical_fit_predict_count': 0, 'reviewer_count': 0}
        batch.write_json(output / 'summary.json', result)
        print(json.dumps({key: value for key, value in result.items() if key not in {'source_identities', 'outputs'}}), flush=True)
        print(str(output), flush=True)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
