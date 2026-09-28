from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage042_holding_labels'
OUTPUT = ROOT / 'artifacts' / STAGE
FREEZE = ROOT / 'stages/stage042_input_freeze.json'
CONTRACT = ROOT / 'stages/20260906_1149_stage042_canonical_holding_labels_contract.md'
SNAPSHOT = ROOT / 'artifacts/stage041c_label_collection/20260906_113658_906705'
LEGACY = ROOT / 'artifacts/stage041b_holding_labels'
CANARY = '513f85cf5e472350c12c3e644cc631ad1d668c6ba09a078bb84ecbd22cdbc3ea'


def load(name):
    spec = importlib.util.spec_from_file_location('canonical042_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def inherited_ids():
    with (SNAPSHOT / 'observations.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    ids = {row['observation_id'] for row in rows if row['label_status'] == 'verified'}
    if len(rows) != 1002 or len({r['observation_id'] for r in rows}) != 1002 or len(ids) != 14 or CANARY in ids:
        raise ValueError('canonical_inherited_inventory')
    return ids


def collect_inputs():
    files = load('stage041b_numeric_inventory_labels').adapted().collect_inputs()
    files.update(canonical_runner=Path(__file__).resolve(), canonical_inventory=ROOT / 'tools/stage042_canonical_inventory.py',
        canonical_tests=ROOT / 'tests/test_stage042_canonical_inventory.py', canonical_runner_tests=ROOT / 'tests/test_stage042_holding_labels.py',
        canonical_contract=CONTRACT, inherited_collection_summary=SNAPSHOT / 'summary.json',
        inherited_input_manifest=LEGACY / 'input_manifest.json', inherited_input_freeze=ROOT / 'stages/stage041b_input_freeze.json')
    summary = json.loads((SNAPSHOT / 'summary.json').read_text())
    for index, identity in enumerate([*summary['source_identities'].values(), *summary['outputs'].values()]):
        files[f'inherited_source/{index}'] = Path(identity['path'])
    for identifier in sorted(inherited_ids()):
        root = LEGACY / 'jobs' / identifier
        for name in json.loads((root / 'archive_receipt.json').read_text()):
            files[f'inherited_archive/{identifier}/{name}'] = root / (name + '.csv.gz')
    for path in sorted((LEGACY / 'jobs' / CANARY).rglob('*')):
        if path.is_file():
            files['gold_failure/' + str(path.relative_to(LEGACY))] = path
    files['failed_continuation_receipt'] = LEGACY / 'batches/0002/failure.json'
    return dict(sorted(files.items()))


def adapted():
    module = load('stage041b_numeric_inventory_labels').adapted()
    original_load = module.load
    canonical = load('stage042_canonical_inventory')

    def local_load(name):
        value = original_load(name)
        if name == 'stage039_scoped_exit':
            value.current_inventory = canonical.current_inventory
        return value

    module.load = local_load
    module.STAGE, module.OUTPUT, module.FREEZE = STAGE, OUTPUT, FREEZE
    module.collect_inputs = collect_inputs
    return module


def select_jobs(jobs, completed, mode, limit):
    ids = [job['observation_id'] for job in jobs]
    if len(ids) != len(set(ids)) or not set(completed).issubset(ids) or limit < 1:
        raise ValueError('canonical_job_selection_identity')
    if mode == 'next' and CANARY not in completed:
        raise ValueError('canonical_gold_canary_incomplete')
    selected = [job for job in jobs if job['observation_id'] not in completed
                and (mode == 'next' or job['observation_id'] == CANARY)]
    return selected[:limit]


def verify_inherited(expected, jobs):
    legacy = load('stage041b_numeric_inventory_labels').adapted(); _, runner = legacy.configured()
    manifest = json.loads((LEGACY / 'input_manifest.json').read_text())
    runner.validate_frozen_input_contract(legacy.FREEZE, manifest); runner.validate_current_input_manifest(manifest)
    summary = json.loads((SNAPSHOT / 'summary.json').read_text())
    if summary['verified'] != 14 or summary['training_ready'] or summary['planned'] != 1002:
        raise ValueError('canonical_inherited_snapshot_status')
    for identity in [*summary['source_identities'].values(), *summary['outputs'].values()]:
        if runner._file_identity(Path(identity['path'])) != identity:
            raise ValueError('canonical_inherited_source_changed')
    values = {}; selected_ids = inherited_ids()
    for job in jobs:
        identifier = job['observation_id']
        if identifier not in selected_ids:
            continue
        root = LEGACY / 'jobs' / identifier
        label = json.loads((root / 'label.json').read_text())
        if label != legacy.validate_job(job, root, manifest, expected, archived=True):
            raise ValueError('canonical_inherited_label_recomputation')
        values[identifier] = label
    if set(values) != selected_ids:
        raise ValueError('canonical_inherited_plan_mismatch')
    return values


def completed_labels(module, manifest, expected, jobs):
    inherited = verify_inherited(expected, jobs)
    completed = dict(inherited)
    directory = OUTPUT / 'jobs'
    if directory.exists() and {path.name for path in directory.iterdir()} - {job['observation_id'] for job in jobs}:
        raise ValueError('canonical_unknown_job_directory')
    for job in jobs:
        identifier = job['observation_id']; root = directory / identifier
        if not root.exists():
            continue
        if identifier in inherited:
            raise ValueError('canonical_inherited_job_rerun')
        if not (root / 'label.json').exists():
            raise ValueError('canonical_unfinished_job:' + identifier)
        label = json.loads((root / 'label.json').read_text())
        if label != module.validate_job(job, root, manifest, expected, archived=True):
            raise ValueError('canonical_completed_label_changed')
        completed[identifier] = label
    return completed


def run_process(item):
    paths, command, environment = item
    started = time.monotonic()
    with paths['log'].open('wb') as stream:
        child = subprocess.run(command, cwd=paths['runtime'], env=environment, stdout=stream, stderr=subprocess.STDOUT)
    return child.returncode, time.monotonic() - started


def run_batch(mode, limit, workers):
    module = adapted(); base, runner = module.configured(); batch = load('stage004_label_batch')
    module.verify_panel(runner); jobs = module.read_plan()['jobs']
    manifest = runner.build_input_manifest(); runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    OUTPUT.mkdir(mode=0o700, exist_ok=True)
    manifest_path = OUTPUT / 'input_manifest.json'
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise ValueError('canonical_manifest_changed')
    else:
        batch.write_json(manifest_path, manifest)
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'stage': STAGE, 'mode': mode}, stream)
    results, batch_root = [], None
    try:
        expected = load('stage007a_runtime_equivalence').expected_frames('A0', manifest['formal_identity'])
        completed = completed_labels(module, manifest, expected, jobs)
        selected = select_jobs(jobs, completed, mode, limit)
        if not selected:
            print(json.dumps({'status': 'no_pending_jobs', 'completed': len(completed)}), flush=True)
            return
        workers = min(workers, len(selected), 3)
        batches = OUTPUT / 'batches'; batches.mkdir(exist_ok=True)
        batch_root = batches / f'{len(list(batches.iterdir())) + 1:04d}'; batch_root.mkdir()
        batch.write_json(batch_root / 'selection.json', {'mode': mode, 'ids': [job['observation_id'] for job in selected],
            'workers': workers, 'previous_completed': len(completed), 'inherited_count': 14,
            'file_contract_sha256': manifest['file_contract_sha256']})
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        archiver = batch.load('canonical_archive', batch.V4 / 'tools/stage006_prefix_equivalence.py')
        for offset in range(0, len(selected), workers):
            wave = selected[offset:offset + workers]; prepared = []
            try:
                for job in wave:
                    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
                        raise ValueError('canonical_disk_reserve')
                    root = OUTPUT / 'jobs' / job['observation_id']; database = manifest['files']['source_database']
                    paths = runner.prepare_stage002_worker_root(root, source_database=Path(database['path']),
                                                                expected_database_sha256=database['sha256'])
                    prepared.append((job, paths))
                    preflight.write_sandbox_profile(paths['profile'], root)
                commands = []
                for job, paths in prepared:
                    command = ['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
                        '-I', '-S', '-B', str(Path(__file__).resolve()), '--worker', '--observation-id', job['observation_id'],
                        '--worker-root', str(paths['worker_root']), '--manifest', str(manifest_path)]
                    commands.append((paths, command, preflight.expected_worker_environment(paths['runtime'])))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    outcomes = list(pool.map(run_process, commands))
                failed = []
                for (job, paths), (code, seconds) in zip(prepared, outcomes):
                    root = paths['worker_root']
                    try:
                        if code:
                            raise ValueError(f'canonical_worker_failed:{code}')
                        label = module.validate_job(job, root, manifest, expected)
                        receipt = json.loads(paths['receipt'].read_text())
                        archives = {name: archiver.archive_csv(root / (name + '.csv'), identity)
                                    for name, identity in receipt['frames'].items()}
                        batch.write_json(root / 'archive_receipt.json', archives)
                        batch.write_json(root / 'label.json', label)
                        results.append({'observation_id': job['observation_id'], 'status': 'passed', 'worker_seconds': seconds})
                    except BaseException as exc:
                        error = {'observation_id': job['observation_id'], 'status': 'failed', 'error': str(exc),
                                 'traceback': traceback.format_exc()}
                        batch.write_json(root / 'failure.json', error); failed.append(error); results.append(error)
                    print(json.dumps(results[-1]), flush=True)
                if failed:
                    raise ValueError('canonical_wave_has_failure')
            finally:
                for _, paths in prepared:
                    if paths['runtime'].exists():
                        shutil.rmtree(paths['runtime'])
        runner.validate_current_input_manifest(manifest)
        summary = {'stage': STAGE, 'status': 'passed', 'mode': mode, 'results': results,
            'new_completed': len(results), 'inherited_count': 14, 'total_completed': len(completed) + len(results),
            'planned': len(jobs), 'training_ready': len(completed) + len(results) == len(jobs),
            'historical_fit_predict_count': 0, 'reviewer_count': 0}
        batch.write_json(batch_root / 'summary.json', summary); print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if batch_root:
            batch.write_json(batch_root / 'failure.json', {'error': str(exc), 'results': results, 'traceback': traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true'); mode.add_argument('--canary', action='store_true')
    mode.add_argument('--next', action='store_true'); mode.add_argument('--worker', action='store_true')
    parser.add_argument('--limit', type=int, default=12); parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--observation-id'); parser.add_argument('--worker-root', type=Path); parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.worker:
        module = adapted(); job = next(job for job in module.read_plan()['jobs'] if job['observation_id'] == args.observation_id)
        if job['observation_id'] in inherited_ids():
            raise ValueError('canonical_worker_inherited_job')
        audit = {}; base, runner = module.configured(job, audit); args.arm = 'A'
        try:
            base.run_worker(args)
        finally:
            runner._write_json_exclusive(args.worker_root / 'exit_audit.json', audit)
    elif args.freeze:
        module = adapted(); _, runner = module.configured(); module.verify_panel(runner)
        manifest = runner.build_input_manifest(); runner.validate_input_manifest_payload(manifest)
        load('stage004_label_batch').verify_baseline_inputs(manifest)
        expected = load('stage007a_runtime_equivalence').expected_frames('A0', manifest['formal_identity'])
        verify_inherited(expected, module.read_plan()['jobs'])
        runner.validate_current_input_manifest(manifest)
        value = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
            'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
        value['execution_authorized'] = True
        load('stage004_label_batch').write_json(FREEZE, value); print(json.dumps(value), flush=True)
    else:
        if not 1 <= args.workers <= 3 or args.limit < 1:
            raise ValueError('canonical_batch_arguments')
        run_batch('canary' if args.canary else 'next', 1 if args.canary else args.limit, args.workers)


if __name__ == '__main__':
    main()
