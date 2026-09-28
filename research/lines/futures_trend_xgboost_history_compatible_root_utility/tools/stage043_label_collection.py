from __future__ import annotations

from collections import Counter
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'stages/20260906_1157_stage043_joint_label_collection_contract.md'


def load(name):
    spec = importlib.util.spec_from_file_location('collection043_' + name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def assemble(jobs, features, labels, inherited):
    import pandas as pd

    columns = ('observation_id', 'date', 'product_vt_symbol', 'vt_symbol', *load('stage040_holding_panel').FEATURES)
    if (tuple(features.columns) != columns or features.observation_id.duplicated().any()
            or set(features.observation_id) != {job['observation_id'] for job in jobs}
            or not set(inherited).issubset(labels)):
        raise ValueError('joint_label_feature_or_owner_inventory')
    rows, ready = load('stage041c_label_collection').label_rows(jobs, labels)
    for row in rows:
        identifier = row['observation_id']
        row['label_source_stage'] = ('stage041b_holding_labels' if identifier in inherited else 'stage042_holding_labels') if identifier in labels else ''
    return features.merge(pd.DataFrame(rows), on='observation_id', validate='one_to_one'), ready


def main():
    import pandas as pd

    batch = load('stage004_label_batch'); current = load('stage042_holding_labels'); module = current.adapted()
    _, runner = module.configured()
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'stage': 'stage043_label_collection'}, stream)
    try:
        manifest_path = current.OUTPUT / 'input_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        runner.validate_frozen_input_contract(current.FREEZE, manifest)
        runner.validate_current_input_manifest(manifest); module.verify_panel(runner)
        plan = module.read_plan(); jobs = plan['jobs']; inherited = current.inherited_ids()
        paths = [Path(__file__).resolve(), ROOT / 'tests/test_stage043_label_collection.py', CONTRACT,
                 current.FREEZE, manifest_path, current.SNAPSHOT / 'summary.json', current.LEGACY / 'input_manifest.json',
                 ROOT / 'stages/stage041b_input_freeze.json']
        paths.extend(module.PANEL / name for name in ('summary.json', 'jobs.json', 'features.csv', 'model_spec.json', 'monthly_inventory.json'))
        for job in jobs:
            base = current.LEGACY if job['observation_id'] in inherited else current.OUTPUT
            root = base / 'jobs' / job['observation_id']
            if (root / 'label.json').exists():
                paths.extend(root / name for name in ('label.json', 'receipt.json', 'archive_receipt.json', 'exit_audit.json'))
        identities = {str(path): runner._file_identity(path) for path in paths}
        expected = load('stage007a_runtime_equivalence').expected_frames('A0', manifest['formal_identity'])
        labels = current.completed_labels(module, manifest, expected, jobs)
        features = pd.read_csv(module.PANEL / 'features.csv', float_precision='round_trip')
        dataset, ready = assemble(jobs, features, labels, inherited)
        metrics = []
        for job in jobs:
            label = labels.get(job['observation_id'])
            if label is None:
                continue
            metrics.append({key: job[key] for key in ('observation_id', 'root_id', 'date', 'end_date', 'vt_symbol', 'direction')}
                | {'label_source_stage': 'stage041b_holding_labels' if job['observation_id'] in inherited else 'stage042_holding_labels'}
                | {f'{arm}_{key}': value for arm in ('A','E') for key,value in label[arm + '_metrics'].items()})
        for path, identity in identities.items():
            if runner._file_identity(Path(path)) != identity:
                raise ValueError('joint_label_source_drift')
        runner.validate_current_input_manifest(manifest)
        expected_counts = Counter(job['root_id'] for job in jobs)
        complete_counts = Counter(label['root_id'] for label in labels.values())
        output = ROOT / 'artifacts/stage043_label_collection' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        output.mkdir(parents=True, exist_ok=False)
        for name, frame in [('observations',dataset),('counterfactual_metrics',pd.DataFrame(metrics))]:
            with (output / (name + '.csv')).open('x') as stream:
                frame.to_csv(stream,index=False,float_format='%.17g')
        summary = {'stage': 'stage043_label_collection', 'status': 'passed', 'verified': len(labels), 'planned': len(jobs),
            'inherited_verified': len(inherited), 'canonical_verified': len(labels) - len(inherited), 'pending': len(jobs) - len(labels),
            'fully_verified_roots': sum(complete_counts[k] == n for k,n in expected_counts.items()),
            'roots_with_any_verified_observation': len(complete_counts), 'total_observed_mature_roots': len(expected_counts),
            'original_root_inventory': len(plan['roots']), 'unobserved_censored_roots_preserved_in_plan':
                sum(root['status'].startswith('right_censored') for root in plan['roots']),
            'training_ready': ready, 'unresolved_current_job_ids': [], 'source_identities': identities,
            'outputs': {name: runner._file_identity(output / name) for name in ('observations.csv', 'counterfactual_metrics.csv')},
            'file_contract_sha256': manifest['file_contract_sha256'], 'new_replay_count': 0,
            'historical_fit_predict_count': 0, 'reviewer_count': 0}
        batch.write_json(output / 'summary.json', summary)
        print(json.dumps({key:value for key,value in summary.items() if key not in {'source_identities','outputs'}}),flush=True)
        print(str(output),flush=True)
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
