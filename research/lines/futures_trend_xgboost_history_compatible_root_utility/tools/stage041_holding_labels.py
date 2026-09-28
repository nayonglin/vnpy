from __future__ import annotations

import argparse
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
STAGE = 'stage041_holding_labels'
OUTPUT = ROOT / 'artifacts' / STAGE
PANEL = ROOT / 'artifacts/stage040_holding_panel'
WINDOWS = ROOT / 'artifacts/stage037_calendar_window/windows.csv'
FREEZE = ROOT / 'stages/stage041_input_freeze.json'
CONTRACT = ROOT / 'stages/20260906_1109_stage041_holding_labels_contract.md'


def load(name):
    spec = importlib.util.spec_from_file_location('labels041_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def read_plan():
    plan = json.loads((PANEL / 'jobs.json').read_text())
    jobs = plan['jobs']
    ids = [job['observation_id'] for job in jobs]
    if (len(jobs) != 1002 or len(set(ids)) != len(ids) or not set(plan['canary_ids']).issubset(ids)
            or any(job['status'] != 'mature' or job['end_date'] <= job['date'] for job in jobs)):
        raise ValueError('holding_label_plan_invalid')
    return plan


def collect_inputs():
    control, panel = load('stage039_exit_controls'), load('stage040_holding_panel')
    files = control.collect_inputs()
    files.update(holding_label_runner=Path(__file__).resolve(), holding_label_tests=ROOT / 'tests/test_stage041_holding_labels.py',
        holding_label_contract=CONTRACT, holding_label_gate=ROOT / 'tools/stage039_scoped_exit.py')
    files.update({f'holding_label_source/{index}': path for index, path in enumerate(panel.source_paths())})
    for name in ('features.csv', 'jobs.json', 'monthly_inventory.json', 'model_spec.json', 'summary.json'):
        files['holding_label_panel_' + name] = PANEL / name
    for arm in ('A0', 'E'):
        root = control.OUTPUT / 'workers' / arm
        for path in sorted(root.iterdir()):
            if path.name in {'receipt.json', 'exit_audit.json', 'archive_receipt.json'} or path.name.endswith('.csv.gz'):
                files[f'holding_label_control/{arm}/{path.name}'] = path
    return dict(sorted(files.items()))


def execution_price(intent, day):
    with WINDOWS.open() as stream:
        rows = [row for row in csv.DictReader(stream) if row['date'] == intent['decision_date']
                and row['vt_symbol'] == intent['vt_symbol']]
    if len(rows) != 1:
        raise ValueError('holding_label_execution_window')
    row = rows[0]
    if (row['status'] != 'source_proxy_qualified_not_execution' or day != row['next_calendar_day']
            or float(row['requested_volume']) != intent['volume'] or float(row['first_volume']) < intent['volume']):
        raise ValueError('holding_label_execution_identity')
    return {'price': float(row['first_open']), 'first_time': row['first_time'], 'fill_date': day,
            'source': 'frozen_first_minute_proxy'}


def check_observation(job, row, book, peak):
    if row != job['snapshot'] or book != job['inventory'] or peak != job['equity_peak']:
        raise ValueError('holding_label_current_state_changed')
    values = load('stage040_holding_panel').visible_features(row, book, peak)
    if values != job['features']:
        raise ValueError('holding_label_current_features_changed')
    return values


def configured(job=None, audit_ref=None):
    base, runner = load('stage004_label_batch').configured()
    base.STAGE = runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = len(collect_inputs())
    original_load = runner.load_v1_runner

    def local_v1():
        v1 = original_load()
        if job is None:
            return v1
        v1.END = v1.pd.Timestamp(job['end_date'])
        original_install = v1._install_correlation_trace_instrumentation

        def instrument(strategy_class):
            correlation_restore = original_install(strategy_class)
            module = load('stage039_scoped_exit')
            observation = module.observer()
            peak, selected = 150000., False

            def choose(strategy, bars):
                nonlocal peak, selected
                peak = max(peak, float(strategy.estimated_equity))
                day = strategy.strategy_engine.datetime.strftime('%Y-%m-%d')
                if day != job['date']:
                    return []
                if selected:
                    raise ValueError('holding_label_repeated_observation')
                selected = True
                row = next(item for item in observation.snapshot(strategy, bars)
                           if item['product_vt_symbol'] == job['product_vt_symbol'])
                book = {symbol: item for symbol, item in module.current_inventory(strategy).items()
                        if strategy.source_symbol_by_contract[symbol] == job['product_vt_symbol']}
                values = check_observation(job, row, book, peak)
                audit_ref['observation'] = {'snapshot': row, 'inventory': book, 'features': values, 'equity_peak': peak}
                return [(row, book)]

            engine_class = getattr(sys.modules[strategy_class.__module__], 'Stage847StopRetryEngine')
            gate = module.install_gate(strategy_class, engine_class, choose, execution_price)
            audit_ref['gate'] = gate.__enter__()

            def restore():
                try:
                    gate.__exit__(None, None, None)
                finally:
                    correlation_restore()
            return restore

        v1._install_correlation_trace_instrumentation = instrument
        return v1

    runner.load_v1_runner = local_v1
    return base, runner


def verify_panel(runner):
    summary = json.loads((PANEL / 'summary.json').read_text())
    if summary['status'] != 'panel_ready_not_labels_or_model':
        raise ValueError('holding_panel_not_ready')
    for identity in [*summary['source_identities'].values(), *summary['outputs'].values()]:
        if runner._file_identity(Path(identity['path'])) != identity:
            raise ValueError('holding_panel_changed')


def reconcile_account(frames, receipt, manifest):
    batch = load('stage004_label_batch')
    resolver = batch.load('holding_label_units', Path(manifest['files']['production_portfolio/contract_metadata.py']['path']))
    mapping = receipt['contract_products']; symbols = sorted(mapping)
    zero = {symbol: 0 for symbol in symbols}
    metadata = resolver.build_resolved_metadata(symbols, zero, zero, zero, mapping,
                                                Path(manifest['files']['contract_metadata']['path']))
    if min(metadata['sizes'].values()) <= 0 or set(metadata['metadata_sources'].values()) != {'tqsdk'}:
        raise ValueError('holding_label_units')
    inventory = load('stage034_fill_inventory')
    _, net, quality = inventory.reconcile(frames['trades'].to_dict('records'),
        frames['positions'].sort_values(['date', 'vt_symbol']).to_dict('records'), metadata['sizes'])
    for row in frames['daily'].itertuples():
        if abs(float(net[str(row.date)[:10]]) - float(row.net_pnl)) > 1e-7:
            raise ValueError('holding_label_account_pnl')
    return quality


def validate_job(job, root, manifest, expected, archived=False):
    batch = load('stage004_label_batch'); base, runner = configured()
    receipt = json.loads((root / 'receipt.json').read_text())
    if (receipt['status'] != 'passed' or receipt['arm'] != 'A' or receipt['stage'] != STAGE
            or receipt['formal_identity'] != manifest['formal_identity']
            or receipt['file_contract_sha256'] != manifest['file_contract_sha256']
            or receipt['formal_replay_call_count'] != 1 or any(receipt['sensitive_counters'].values())
            or receipt['network_connection_attempt_count'] or receipt['audit']['skip_count']):
        raise ValueError('holding_label_receipt')
    collector = load('stage005_label_collection')
    archives = json.loads((root / 'archive_receipt.json').read_text()) if archived else {}
    frames = {}
    if set(receipt['frames']) != set(base.FRAME_NAMES) or (archived and set(archives) != set(base.FRAME_NAMES)):
        raise ValueError('holding_label_frame_inventory')
    for name, identity in receipt['frames'].items():
        if archived:
            path = root / (name + '.csv.gz'); item = archives[name]
            collector.verify_archive(path, item)
            if item['raw_sha256'] != identity['sha256'] or item['raw_size'] != identity['size']:
                raise ValueError('holding_label_archive_binding')
        else:
            path = root / (name + '.csv')
            if runner._file_identity(path) != identity:
                raise ValueError('holding_label_frame_changed')
        frames[name] = batch.read_frame(path)
    audit = json.loads((root / 'exit_audit.json').read_text())
    gate, observation = audit['gate'], audit['observation']
    check_observation(job, observation['snapshot'], observation['inventory'], observation['equity_peak'])
    if (observation['features'] != job['features'] or len(gate['intents']) != 1 or len(gate['fills']) != 1
            or len(gate['resolutions']) != 1 or gate['unfilled_order_ids']):
        raise ValueError('holding_label_action_inventory')
    intent, fill = gate['intents'][0], gate['fills'][0]
    price = execution_price(intent, fill['fill_date'])
    target = frames['trades'][frames['trades'].trade_id.eq(fill['trade_id'])]
    if (intent['decision_date'] != job['date'] or intent['vt_symbol'] != job['vt_symbol']
            or len(target) != 1 or target.iloc[0].order_id != intent['order_id']
            or target.iloc[0].exit_reason != 'research_holding_exit' or float(target.iloc[0].price) != price['price']
            or float(target.iloc[0].volume) != abs(job['snapshot']['actual_positions'][job['vt_symbol']])
            or str(target.iloc[0].date)[:10] != price['fill_date']):
        raise ValueError('holding_label_actual_close')
    prefix = load('stage039_exit_controls').prefix
    load('stage007a_runtime_equivalence').require_frame_equivalence(
        {key: prefix(frame, job['date']) for key, frame in expected.items()},
        {key: prefix(frame, job['date']) for key, frame in frames.items()})
    batch.validate_daily_calendar(expected['daily'], frames['daily'], job['end_date'])
    quality = reconcile_account(frames, receipt, manifest)
    marginal = load('stage040_holding_panel').holding_utility(expected['daily'].to_dict('records'),
        frames['daily'].to_dict('records'), job['date'], job['end_date'], job['account_equity'])
    metrics = base.equity_metrics(frames['daily'], frames['trades'])
    if metrics != receipt['metrics']:
        raise ValueError('holding_label_metrics')
    return {'observation_id': job['observation_id'], 'root_id': job['root_id'], 'status': 'passed',
        'date': job['date'], 'end_date': job['end_date'], 'marginal': marginal,
        'A_metrics': base.equity_metrics(prefix(expected['daily'], job['end_date']), prefix(expected['trades'], job['end_date'])),
        'E_metrics': metrics, 'inventory_quality': quality, 'prefix_seven_exact': True,
        'features_current_exact': True, 'file_contract_sha256': manifest['file_contract_sha256'],
        'plan_sha256': batch.digest(PANEL / 'jobs.json'), 'receipt_sha256': batch.digest(root / 'receipt.json'),
        'exit_audit_sha256': batch.digest(root / 'exit_audit.json')}


def run_batch(mode, limit):
    batch = load('stage004_label_batch'); base, runner = configured()
    verify_panel(runner); plan = read_plan()
    manifest = runner.build_input_manifest(); runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    OUTPUT.mkdir(mode=0o700, exist_ok=True)
    path = OUTPUT / 'input_manifest.json'
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError('holding_label_manifest_changed')
    else:
        batch.write_json(path, manifest)
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'mode': STAGE}, stream)
    results, batch_root = [], None
    try:
        formal = json.loads((load('stage039_exit_controls').OUTPUT / 'workers/A0/receipt.json').read_text())['formal_identity']
        expected = load('stage007a_runtime_equivalence').expected_frames('A0', formal)
        completed = {}
        for job in plan['jobs']:
            root = OUTPUT / 'jobs' / job['observation_id']
            if (root / 'label.json').exists():
                label = json.loads((root / 'label.json').read_text())
                if label != validate_job(job, root, manifest, expected, archived=True):
                    raise ValueError('holding_label_recomputation')
                completed[job['observation_id']] = label
            elif root.exists():
                raise ValueError('holding_label_unfinished_job:' + job['observation_id'])
        if mode == 'next' and not set(plan['canary_ids']).issubset(completed):
            raise ValueError('holding_label_canary_incomplete')
        jobs = [job for job in plan['jobs'] if job['observation_id'] not in completed
                and (mode != 'canary' or job['observation_id'] in plan['canary_ids'])]
        if mode == 'next':
            jobs = jobs[:limit]
        if not jobs:
            print(json.dumps({'status': 'no_pending_jobs', 'completed': len(completed)}), flush=True)
            return
        batches = OUTPUT / 'batches'; batches.mkdir(exist_ok=True)
        batch_root = batches / f'{len(list(batches.iterdir())) + 1:04d}'; batch_root.mkdir()
        batch.write_json(batch_root / 'selection.json', {'mode': mode, 'ids': [job['observation_id'] for job in jobs],
            'file_contract_sha256': manifest['file_contract_sha256'], 'workers': 1})
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        archiver = batch.load('holding_label_archive', batch.V4 / 'tools/stage006_prefix_equivalence.py')
        for job in jobs:
            if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
                raise ValueError('holding_label_disk_reserve')
            root = OUTPUT / 'jobs' / job['observation_id']; started = time.monotonic(); paths = None
            try:
                database = manifest['files']['source_database']
                paths = runner.prepare_stage002_worker_root(root, source_database=Path(database['path']),
                                                            expected_database_sha256=database['sha256'])
                preflight.write_sandbox_profile(paths['profile'], root)
                command = ['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
                    '-I', '-S', '-B', str(Path(__file__).resolve()), '--worker', '--observation-id', job['observation_id'],
                    '--worker-root', str(root), '--manifest', str(path)]
                with paths['log'].open('wb') as stream:
                    child = subprocess.run(command, cwd=paths['runtime'], env=preflight.expected_worker_environment(paths['runtime']),
                                           stdout=stream, stderr=subprocess.STDOUT)
                if child.returncode:
                    raise ValueError(f'holding_label_worker_failed:{child.returncode}')
                label = validate_job(job, root, manifest, expected)
                receipt = json.loads(paths['receipt'].read_text())
                archives = {name: archiver.archive_csv(root / (name + '.csv'), identity)
                            for name, identity in receipt['frames'].items()}
                batch.write_json(root / 'archive_receipt.json', archives)
                batch.write_json(root / 'label.json', label)
                results.append({'observation_id': job['observation_id'], 'seconds': time.monotonic() - started, 'status': 'passed'})
                print(json.dumps(results[-1]), flush=True)
            except BaseException as exc:
                if root.exists():
                    batch.write_json(root / 'failure.json', {'error': str(exc), 'traceback': traceback.format_exc()})
                raise
            finally:
                if paths and paths['runtime'].exists():
                    shutil.rmtree(paths['runtime'])
        runner.validate_current_input_manifest(manifest)
        summary = {'stage': STAGE, 'status': 'passed', 'mode': mode, 'results': results,
            'total_completed': len(completed) + len(results), 'planned': len(plan['jobs']),
            'training_ready': len(completed) + len(results) == len(plan['jobs']), 'model_fit_count': 0, 'reviewer_count': 0}
        batch.write_json(batch_root / 'summary.json', summary); print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if batch_root:
            batch.write_json(batch_root / 'failure.json', {'error': str(exc), 'completed': results, 'traceback': traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true'); mode.add_argument('--canary', action='store_true')
    mode.add_argument('--next', action='store_true'); mode.add_argument('--worker', action='store_true')
    parser.add_argument('--limit', type=int, default=3); parser.add_argument('--observation-id')
    parser.add_argument('--worker-root', type=Path); parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.worker:
        job = next(item for item in read_plan()['jobs'] if item['observation_id'] == args.observation_id)
        audit = {}; base, runner = configured(job, audit); args.arm = 'A'
        try:
            base.run_worker(args)
        finally:
            runner._write_json_exclusive(args.worker_root / 'exit_audit.json', audit)
    elif args.freeze:
        _, runner = configured(); verify_panel(runner)
        manifest = runner.build_input_manifest(); runner.validate_input_manifest_payload(manifest)
        load('stage004_label_batch').verify_baseline_inputs(manifest)
        value = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
            'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
        value['execution_authorized'] = True
        load('stage004_label_batch').write_json(FREEZE, value); print(json.dumps(value), flush=True)
    else:
        if args.limit <= 0:
            raise ValueError('holding_label_invalid_limit')
        run_batch('canary' if args.canary else 'next', args.limit)


if __name__ == '__main__':
    main()
