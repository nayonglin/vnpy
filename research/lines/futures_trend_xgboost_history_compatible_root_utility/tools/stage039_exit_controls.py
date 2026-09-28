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
STAGE = 'stage039_exit_controls'
OUTPUT = ROOT / 'artifacts' / STAGE
FREEZE = ROOT / 'stages/stage039_input_freeze.json'
CONTRACT = ROOT / 'stages/20260906_1024_stage039_scoped_exit_contract.md'
PARENT = ROOT / 'artifacts/stage038_execution_source'
WINDOWS = ROOT / 'artifacts/stage037_calendar_window/windows.csv'


def load(name):
    spec = importlib.util.spec_from_file_location('control039_' + name, ROOT / 'tools' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def target_window():
    with WINDOWS.open() as stream:
        rows = sorted(csv.DictReader(stream), key=lambda row: (row['date'], row['product_vt_symbol'], row['vt_symbol']))
    if len(rows) != 1002 or any(row['status'] != 'source_proxy_qualified_not_execution' for row in rows):
        raise ValueError('exit_control_window_inventory')
    return rows[0]


def collect_inputs():
    files = {key: Path(item['path']) for key, item in json.loads((PARENT / 'input_manifest.json').read_text())['files'].items()}
    files.update(exit_runner=Path(__file__).resolve(), exit_gate=ROOT / 'tools/stage039_scoped_exit.py',
                 exit_tests=ROOT / 'tests/test_stage039_scoped_exit.py', exit_control_tests=ROOT / 'tests/test_stage039_exit_controls.py',
                 exit_contract=CONTRACT, exit_parent_manifest=PARENT / 'input_manifest.json',
                 exit_parent_summary=PARENT / 'summary.json', exit_parent_freeze=ROOT / 'stages/stage038_input_freeze.json')
    production = Path('/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting/downloaded_futures')
    for index, name in enumerate(('tqsdk_stage506_next_real_forward_risk_signal_frontier',
                                  'tqsdk_stage452_true_path_fallback_1455', 'tqsdk_stage448_minute_session_rebuild_batch')):
        root = production / name
        for path in sorted(root.rglob('*')):
            if path.is_file():
                files[f'execution_raw/{index}/{path.relative_to(root)}'] = path
    return dict(sorted(files.items()))


def configured(control='A0', audit_ref=None):
    if control not in ('A0', 'E'):
        raise ValueError('exit_control_unknown')
    base, runner = load('stage004_label_batch').configured()
    base.STAGE = runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = len(collect_inputs())
    original_load = runner.load_v1_runner

    def local_v1():
        v1 = original_load()
        if control == 'E':
            v1.END = v1.pd.Timestamp(target_window()['next_calendar_day'])
        original_install = v1._install_correlation_trace_instrumentation

        def instrument(strategy_class):
            correlation_restore = original_install(strategy_class)
            module = load('stage039_scoped_exit')
            target = target_window() if control == 'E' else None
            selected = set()

            def choose(strategy, bars):
                day = strategy.strategy_engine.datetime.strftime('%Y-%m-%d')
                if day != target['date']:
                    return []
                if day in selected:
                    raise ValueError('exit_fixed_event_revisited')
                selected.add(day)
                rows = module.observer().snapshot(strategy, bars)
                row = next(item for item in rows if item['product_vt_symbol'] == target['product_vt_symbol'])
                if row['actual_positions'] != {target['vt_symbol']: float(target['actual_volume'])}:
                    raise ValueError('exit_fixed_position_changed')
                inventory = module.current_inventory(strategy)
                inventory = {symbol: item for symbol, item in inventory.items()
                             if strategy.source_symbol_by_contract[symbol] == row['product_vt_symbol']}
                return [(row, inventory)]

            def provider(intent, day):
                row = target_window()
                if (day != row['next_calendar_day'] or intent['vt_symbol'] != row['vt_symbol']
                        or intent['decision_date'] != row['date'] or intent['volume'] != float(row['requested_volume'])
                        or float(row['first_volume']) < intent['volume']):
                    raise ValueError('exit_fixed_execution_window_changed')
                return {'price': float(row['first_open']), 'first_time': row['first_time'], 'fill_date': day,
                        'source': 'frozen_first_minute_proxy'}

            engine_class = getattr(sys.modules[strategy_class.__module__], 'Stage847StopRetryEngine')
            gate = module.install_gate(strategy_class, engine_class, choose if control == 'E' else None, provider)
            audit = gate.__enter__()
            if audit_ref is not None:
                audit_ref['gate'] = audit

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


def verify_parent():
    parent = load('stage038_execution_source')
    runner = parent.configured()
    manifest = json.loads((PARENT / 'input_manifest.json').read_text())
    runner.validate_frozen_input_contract(parent.FREEZE, manifest)
    runner.validate_current_input_manifest(manifest)
    summary = json.loads((PARENT / 'summary.json').read_text())
    if summary['status'] != 'current_legacy_prices_compatible_not_execution':
        raise ValueError('exit_price_parent_unqualified')
    for item in summary['outputs'].values():
        if runner._file_identity(Path(item['path'])) != item:
            raise ValueError('exit_price_parent_changed')


def prefix(frame, date):
    if frame.empty:
        return frame
    key = next((name for name in ('date', 'decision_date', 'datetime') if name in frame), None)
    if key is None:
        raise ValueError('exit_control_frame_date_missing')
    return frame[frame[key].astype(str).str[:10].le(date)].reset_index(drop=True)


def verify_exit(frames, expected, audit, receipt, manifest):
    import pandas as pd

    if (len(audit['intents']) != 1 or len(audit['fills']) != 1 or len(audit['resolutions']) != 1
            or audit['unfilled_order_ids']):
        raise ValueError('exit_control_action_count')
    target = target_window()
    equivalence = load('stage007a_runtime_equivalence')
    equivalence.require_frame_equivalence({key: prefix(value, target['date']) for key, value in expected.items()},
                                         {key: prefix(value, target['date']) for key, value in frames.items()})
    fill = audit['fills'][0]
    observed = frames['trades'][frames['trades'].trade_id.eq(fill['trade_id'])]
    if (len(observed) != 1 or observed.iloc[0].order_id != audit['intents'][0]['order_id']
            or observed.iloc[0].exit_reason != 'research_holding_exit'
            or observed.iloc[0].vt_symbol != target['vt_symbol'] or float(observed.iloc[0].price) != float(target['first_open'])
            or float(observed.iloc[0].volume) != abs(float(target['actual_volume']))
            or str(observed.iloc[0].date)[:10] != target['next_calendar_day']):
        raise ValueError('exit_control_trade_identity')
    if (frames['daily'].date.astype(str).str[:10].tolist()
            != prefix(expected['daily'], target['next_calendar_day']).date.astype(str).str[:10].tolist()):
        raise ValueError('exit_control_calendar')
    inventory = load('stage034_fill_inventory')
    batch = load('stage004_label_batch')
    resolver = batch.load('exit_unit_resolver', Path(manifest['files']['production_portfolio/contract_metadata.py']['path']))
    mapping = receipt['contract_products']; symbols = sorted(mapping)
    resolved = resolver.build_resolved_metadata(symbols, {s: 0 for s in symbols}, {s: 0 for s in symbols},
        {s: 0 for s in symbols}, mapping, Path(manifest['files']['contract_metadata']['path']))
    if any(size <= 0 for size in resolved['sizes'].values()) or set(resolved['metadata_sources'].values()) != {'tqsdk'}:
        raise ValueError('exit_control_units')
    positions = frames['positions'].copy().sort_values(['date', 'vt_symbol'])
    _, net, quality = inventory.reconcile(frames['trades'].to_dict('records'), positions.to_dict('records'), resolved['sizes'])
    for row in frames['daily'].itertuples():
        if abs(float(net[str(row.date)[:10]]) - float(row.net_pnl)) > 1e-7:
            raise ValueError('exit_control_account_pnl')
    specific = positions[positions.date.astype(str).str[:10].eq(target['next_calendar_day'])
                         & positions.vt_symbol.eq(target['vt_symbol'])]
    if len(specific) != 1 or float(specific.iloc[0].commission + specific.iloc[0].slippage) < fill['cost']:
        raise ValueError('exit_control_cost_ledger')
    return {'prefix_all_seven_frames_exact': True, 'fill_inventory': quality, 'action': audit,
            'reference_prefix_metrics': batch.configured()[0].equity_metrics(
                prefix(expected['daily'], target['next_calendar_day']), prefix(expected['trades'], target['next_calendar_day']))}


def run_parent():
    verify_parent()
    batch = load('stage004_label_batch')
    base, runner = configured()
    if OUTPUT.exists():
        raise ValueError('exit_control_campaign_exists')
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise ValueError('exit_control_disk_reserve')
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'mode': STAGE}, stream)
    results = {}
    try:
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / 'input_manifest.json', manifest)
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        archiver = batch.load('exit_control_archive', batch.V4 / 'tools/stage006_prefix_equivalence.py')
        equivalence = load('stage007a_runtime_equivalence')
        for control in ('A0', 'E'):
            root = OUTPUT / 'workers' / control
            database = manifest['files']['source_database']
            paths = runner.prepare_stage002_worker_root(root, source_database=Path(database['path']),
                                                       expected_database_sha256=database['sha256'])
            started = time.monotonic()
            try:
                preflight.write_sandbox_profile(paths['profile'], root)
                command = ['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
                           '-I', '-S', '-B', str(Path(__file__).resolve()), '--worker', '--control', control,
                           '--worker-root', str(root), '--manifest', str(OUTPUT / 'input_manifest.json')]
                with paths['log'].open('wb') as stream:
                    child = subprocess.run(command, cwd=paths['runtime'], env=preflight.expected_worker_environment(paths['runtime']),
                                           stdout=stream, stderr=subprocess.STDOUT)
                if child.returncode:
                    raise ValueError(f'exit_control_worker_failed:{control}:{child.returncode}')
                receipt = json.loads(paths['receipt'].read_text())
                if (receipt['status'] != 'passed' or receipt['arm'] != 'A' or receipt['stage'] != STAGE
                        or receipt['file_contract_sha256'] != manifest['file_contract_sha256']
                        or receipt['formal_identity'] != manifest['formal_identity']
                        or receipt['formal_replay_call_count'] != 1 or any(receipt['sensitive_counters'].values())
                        or receipt['network_connection_attempt_count'] != 0 or receipt['audit']['skip_count'] != 0):
                    raise ValueError('exit_control_worker_receipt')
                for name, identity in receipt['frames'].items():
                    if runner._file_identity(root / (name + '.csv')) != identity:
                        raise ValueError('exit_control_output_changed')
                observed = base.read_frames(root)
                expected = equivalence.expected_frames('A0', receipt['formal_identity'])
                audit = json.loads((root / 'exit_audit.json').read_text())['gate']
                if control == 'A0':
                    equivalence.require_frame_equivalence(expected, observed)
                    if (receipt['metrics'] != base.equity_metrics(expected['daily'], expected['trades'])
                            or any(audit.values())):
                        raise ValueError('exit_disabled_changed_A')
                    qualification = {'all_seven_frames_exact': True, 'action_count': 0}
                else:
                    qualification = verify_exit(observed, expected, audit, receipt, manifest)
                archives = {name: archiver.archive_csv(root / (name + '.csv'), identity)
                            for name, identity in receipt['frames'].items()}
                batch.write_json(root / 'archive_receipt.json', archives)
                results[control] = {'status': 'passed', 'metrics': receipt['metrics'], 'qualification': qualification,
                                    'seconds': time.monotonic() - started, 'receipt_sha256': batch.digest(paths['receipt']),
                                    'exit_audit_identity': runner._file_identity(root / 'exit_audit.json')}
                print(json.dumps({'control': control, 'status': 'passed', 'seconds': results[control]['seconds']}), flush=True)
                del observed, expected
            finally:
                if paths['runtime'].exists():
                    shutil.rmtree(paths['runtime'])
        runner.validate_current_input_manifest(manifest)
        summary = {'stage': STAGE, 'status': 'engineering_controls_passed_not_model', 'results': results,
                   'formal_replay_call_count': 2, 'new_label_count': 0, 'new_xgboost_fit_count': 0,
                   'reviewer_count': 0, 'model_candidate': False, 'file_contract_sha256': manifest['file_contract_sha256']}
        batch.write_json(OUTPUT / 'summary.json', summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if OUTPUT.exists():
            batch.write_json(OUTPUT / 'failure.json', {'error': str(exc), 'results': results, 'traceback': traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true'); mode.add_argument('--run', action='store_true')
    mode.add_argument('--worker', action='store_true')
    parser.add_argument('--control', choices=['A0', 'E'], default='A0')
    parser.add_argument('--worker-root', type=Path); parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    if args.worker:
        args.arm = 'A'
        audit = {}
        base, runner = configured(args.control, audit)
        try:
            base.run_worker(args)
        finally:
            runner._write_json_exclusive(args.worker_root / 'exit_audit.json', audit)
    elif args.freeze:
        verify_parent()
        _, runner = configured()
        manifest = runner.build_input_manifest(); runner.validate_input_manifest_payload(manifest)
        load('stage004_label_batch').verify_baseline_inputs(manifest)
        value = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
            'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
        value['execution_authorized'] = True
        load('stage004_label_batch').write_json(FREEZE, value)
        print(json.dumps(value), flush=True)
    else:
        run_parent()


if __name__ == '__main__':
    main()
