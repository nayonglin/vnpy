from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from functools import lru_cache
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
STAGE = 'stage049_holding_full_replay'
OUTPUT = ROOT / 'artifacts' / STAGE
MODEL_OUTPUT = ROOT / 'artifacts/stage044_holding_training'
PANEL = ROOT / 'artifacts/stage040_holding_panel'
FREEZE = ROOT / 'stages/stage049_input_freeze.json'
CONTRACT = ROOT / 'stages/20260906_1706_stage049_holding_full_path_contract.md'
START, END = '2020-01-02', '2026-08-28'
FRAME_NAMES = ('daily', 'trades', 'positions', 'entry_candidates', 'entry_risk', 'stop_retry_events', 'root_features')


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('holding049_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def catalog(summary_sha):
    if not isinstance(summary_sha, str) or not re.fullmatch('[0-9a-f]{64}', summary_sha):
        raise RuntimeError('holding_full_training_summary_sha_required')
    if not MODEL_OUTPUT.is_dir():
        raise RuntimeError('holding_training_campaign_not_complete')
    spec = json.loads((PANEL / 'model_spec.json').read_text())
    jobs = json.loads((PANEL / 'jobs.json').read_text())['jobs']
    months = json.loads((PANEL / 'monthly_inventory.json').read_text())
    return load('stage045_holding_catalog').load_catalog(MODEL_OUTPUT, spec, summary_sha, jobs, months)


def collect_inputs(summary_sha):
    _, spec, evidence = catalog(summary_sha)
    current = load('stage042_holding_labels'); _, prior = current.adapted().configured()
    path = current.OUTPUT / 'input_manifest.json'; manifest = json.loads(path.read_text())
    prior.validate_frozen_input_contract(current.FREEZE, manifest); prior.validate_current_input_manifest(manifest)
    files = {key: Path(value['path']) for key, value in manifest['files'].items()}
    files.update(load('stage046_dynamic_exit_source').collect_inputs())
    files.update(holding_full_contract=CONTRACT, holding_full_prior_manifest=path,
                 holding_full_prior_freeze=current.FREEZE)
    for name in ('stage005_label_collection', 'stage006_monthly_models',
                 'stage008_frozen_inference', 'stage008_model_catalog', 'stage009_path_validation',
                 'stage044_holding_models', 'stage044_holding_training', 'stage045_holding_catalog',
                 'stage045_holding_inference', 'stage046_dynamic_exit_source', 'stage047_current_holding_policy',
                 'stage049_holding_path_validation', 'stage049_holding_full_replay'):
        files['holding_full_tool/' + name] = ROOT / 'tools' / (name + '.py')
        files['holding_full_test/' + name] = ROOT / 'tests' / ('test_' + name + '.py')
    for name in ('20260906_1308_stage045_model_consumption_contract.md',
                 '20260906_1440_stage047_current_holding_policy_contract.md',
                 '20260906_1654_stage048_training_snapshot_identity_contract.md'):
        files['holding_full_contract/' + name] = ROOT / 'stages' / name
    for index, path in enumerate(evidence['files']):
        files[f'holding_training/{index:05}'] = path
    batch = load('stage004_label_batch')
    for name in ('daily.csv', 'receipt.json'):
        files['holding_reference/' + name] = batch.REFERENCE / name
    load('stage044_holding_training').check_versions(spec)
    package = prior.load_metadata_preflight_module().load_preflight_module().python_site_packages() / 'xgboost'
    for path in sorted(package.rglob('*.py')):
        files['holding_xgboost_source/' + str(path.relative_to(package))] = path
    for path in sorted((package / 'lib').glob('*')):
        if path.is_file():
            files['holding_xgboost_native/' + path.name] = path
    return dict(sorted(files.items()))


def configured(input_count=None, summary_sha=None):
    batch = load('stage004_label_batch'); base, runner = batch.configured()
    if input_count is None:
        freeze = json.loads(FREEZE.read_text())
        input_count = freeze['input_file_count']
        if summary_sha != freeze['training_summary_sha256']:
            raise RuntimeError('holding_full_frozen_model_changed')
    base.STAGE = runner.STAGE = STAGE
    runner.collect_input_files = lambda: collect_inputs(summary_sha)
    runner.EXPECTED_INPUT_FILE_COUNT = input_count
    return batch, base, runner


def freeze_inputs(summary_sha):
    files = collect_inputs(summary_sha)
    batch, _, runner = configured(len(files), summary_sha)
    manifest = runner.build_input_manifest(); runner.validate_input_manifest_payload(manifest)
    batch.verify_baseline_inputs(manifest)
    payload = {key: manifest[key] for key in ('schema_version', 'stage', 'line_id', 'input_file_count',
        'input_logical_key_sha256', 'file_contract_sha256', 'runtime_contract_sha256')}
    payload.update(execution_authorized=True, training_summary_sha256=summary_sha)
    batch.write_json(FREEZE, payload)
    print(json.dumps(payload), flush=True)


def inference_guard(preflight, registry, spec, roots, summary_sha, allowed_replays=0):
    _, base, _ = configured(summary_sha=summary_sha)
    cls = load('stage045_holding_inference').holding_guard_class(preflight, base.load_stage003())
    return cls(roots, registry=registry, spec=spec, allowed_formal_replay_count=allowed_replays)


@contextmanager
def install_holding(strategy_class, engine_class, guard, provider):
    policy = load('stage047_current_holding_policy').HoldingPolicy(guard)
    observer = load('stage033_holding_observer'); gate = load('stage039_scoped_exit')
    original = (strategy_class.on_bars, strategy_class.update_trade, engine_class._resolve_trade_price)
    state = {'policy': policy, 'terminal': None, 'contract_products': None,
             'callback_failure': None, 'execution_failure': None, 'methods_restored': False}
    state['provenance'] = {key: observer.method_identity(method) for key, method in
        zip(('on_bars', 'update_trade', 'resolve_trade_price'), original)}
    def price(intent, day):
        try:
            return provider(intent, day)
        except Exception:
            state['execution_failure'] = traceback.format_exc()
            raise
    try:
        with gate.install_gate(strategy_class, engine_class, policy, price) as audit:
            state['gate'] = audit; delegated = strategy_class.on_bars
            def observed(strategy, bars):
                try:
                    result = delegated(strategy, bars)
                    rows = observer.snapshot(strategy, bars)
                    if rows:
                        state['terminal'] = {'states': rows, 'pending_close_volumes': {
                            symbol: sum(gate.number(item['volume']) for item in items)
                            for symbol, items in strategy.pending_close_lots.items()}}
                        state['contract_products'] = dict(strategy.source_symbol_by_contract)
                    return result
                except Exception:
                    state['callback_failure'] = traceback.format_exc()
                    raise
            strategy_class.on_bars = observed
            try:
                yield state
            finally:
                strategy_class.on_bars = delegated
    finally:
        state['methods_restored'] = original == (strategy_class.on_bars, strategy_class.update_trade, engine_class._resolve_trade_price)


def read_csv(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def read_trace(root, expected):
    path = Path(root) / 'holding_trace.json.gz'; identity = expected['file']
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('holding_full_trace_changed')
    raw = path.read_bytes()
    current = {'path': str(path.resolve()), 'size': len(raw), 'mtime_ns': path.stat().st_mtime_ns,
               'sha256': hashlib.sha256(raw).hexdigest()}
    if current != identity:
        raise RuntimeError('holding_full_trace_changed')
    decoded = gzip.decompress(raw)
    if hashlib.sha256(decoded).hexdigest() != expected['raw_sha256']:
        raise RuntimeError('holding_full_trace_decoded_changed')
    return json.loads(decoded)


def validate_worker_receipt(receipt, manifest, summary_sha):
    if (receipt['stage'] != STAGE or receipt['status'] != 'passed' or receipt['arm'] != 'C'
            or receipt['file_contract_sha256'] != manifest['file_contract_sha256']
            or receipt['formal_identity'] != manifest['formal_identity']
            or receipt['training_summary_sha256'] != summary_sha or receipt['formal_replay_call_count'] != 1
            or receipt['network_connection_attempt_count'] or any(receipt['sensitive_counters'].values())
            or receipt['baseline_inference']['load_count'] != 1 or receipt['release_adapter_call_count'] != 1
            or receipt['release_adapter_restored'] is not True or receipt['strategy_methods_restored'] is not True
            or set(receipt['frames']) != set(FRAME_NAMES)):
        raise RuntimeError('holding_full_worker_receipt_invalid')


def run_worker(args):
    batch = load('stage004_label_batch'); _, bootstrap_runner = batch.configured()
    support = bootstrap_runner.load_metadata_preflight_module(); preflight = support.load_preflight_module()
    root = args.worker_root.resolve(strict=True); runtime = root / 'runtime'
    preflight._validate_worker_bootstrap(runtime)
    preflight.prove_external_write_denied(root.parent.parent / 'holding_C_probe')
    sys.path.extend([str(preflight.python_site_packages()), str(WORKSPACE)])
    batch, base, runner = configured(summary_sha=args.training_summary_sha256)
    manifest = json.loads(args.manifest.read_text()); runner.validate_current_input_manifest(manifest)
    database = runtime / '.vntrader/database.db'
    if runner._file_identity(database)['sha256'] != manifest['files']['source_database']['sha256']:
        raise RuntimeError('holding_full_database_copy_changed')
    registry, spec, _ = catalog(args.training_summary_sha256)
    calendar = load('stage049_holding_path_validation').calendar_days(row['date'] for row in read_csv(batch.REFERENCE / 'daily.csv'))
    if calendar[0] != START or calendar[-1] != END:
        raise RuntimeError('holding_full_reference_calendar')
    attestation = preflight._load_release_attestation(runner.RELEASE_ATTESTATION)
    v1 = runner.load_v1_runner(); formal = v1._active_formal_identity()
    if (formal != manifest['formal_identity'] or v1.START.strftime('%Y-%m-%d') != START
            or v1.END.strftime('%Y-%m-%d') != END):
        raise RuntimeError('holding_full_formal_identity_or_period')
    expected = support.validate_frozen_metadata_files(manifest)
    network = preflight.NetworkBlock()
    guard = inference_guard(preflight, registry, spec, (root,), args.training_summary_sha256, 1)
    guard.assert_no_sensitive_modules_loaded()
    runner._write_json_exclusive(root / 'started.json', {'pid': os.getpid(), 'arm': 'C', 'status': 'replaying'})
    with network, guard:
        context, adapter_calls, restored = preflight.import_production_context_with_attestation(attestation)
        candidate = sys.modules[runner.CANDIDATE_MODULE_NAME]
        strategy = context['s901'].s847.QmtRollPortfolioStrategyStage847C9StopRetry
        engine = getattr(sys.modules[strategy.__module__], 'Stage847StopRetryEngine')
        provider = load('stage046_dynamic_exit_source').DynamicExitSource(manifest['files'], database, calendar)
        with support.redirect_metadata_outputs(candidate, root) as targets:
            metadata = context['s901'].s513._metadata()
            restore_trace = v1._install_correlation_trace_instrumentation(strategy)
            try:
                with install_holding(strategy, engine, guard, provider) as state:
                    daily, raw, engine_spec = context['s901']._run_live_c9(metadata, v1.START, v1.END)
            finally:
                restore_trace()
            support.verify_derived_outputs(targets, expected)
        if state['callback_failure'] or state['execution_failure'] or not state['methods_restored']:
            raise RuntimeError('holding_full_callback_failed:' + str(state['callback_failure'] or state['execution_failure']))
        if (float(engine_spec.capital.account_capital) != 150000
                or engine_spec.profile != context['live_config'].OFFICIAL_LIVE_PROFILE_NAME
                or daily.date.astype(str).str[:10].tolist() != calendar or state['terminal'] is None):
            raise RuntimeError('holding_full_engine_spec_or_calendar')
        frames = {'daily': daily, 'root_features': batch.feature_adapter(raw['entry_candidates'], None, formal),
                  **{name: raw[name] for name in base.FRAME_NAMES if name not in {'daily', 'root_features'}}}
        provider.verify_used_inputs()
        trace = {key: state[key] for key in ('gate', 'terminal', 'provenance', 'callback_failure', 'execution_failure')}
        trace.update(states=state['policy'].states, decisions=state['policy'].decisions,
                     source_receipt=provider.receipt(), source_windows=provider.windows)
    if (any(guard.counters.values()) or network.attempts or guard.formal_replay_call_count != 1
            or len(adapter_calls) != 1 or not restored or guard.load_count != 1):
        raise RuntimeError('holding_full_worker_safety_failed')
    identities = {}
    for name, frame in frames.items():
        path = root / (name + '.csv')
        runner._write_bytes_exclusive(path, frame.to_csv(index=False, float_format='%.17g').encode())
        identities[name] = runner._file_identity(path)
    decoded = json.dumps(trace, separators=(',', ':'), allow_nan=False).encode()
    path = root / 'holding_trace.json.gz'; runner._write_bytes_exclusive(path, gzip.compress(decoded, mtime=0))
    receipt = {'stage': STAGE, 'status': 'passed', 'arm': 'C', 'pid': os.getpid(), 'formal_identity': formal,
        'file_contract_sha256': manifest['file_contract_sha256'], 'training_summary_sha256': args.training_summary_sha256,
        'frames': identities, 'trace': {'file': runner._file_identity(path), 'raw_sha256': hashlib.sha256(decoded).hexdigest()},
        'contract_products': state['contract_products'], 'metrics': base.equity_metrics(daily, raw['trades']),
        'baseline_inference': guard.receipt(), 'xgboost_inference': guard.xgboost_receipt(),
        'sensitive_counters': guard.counters, 'formal_replay_call_count': guard.formal_replay_call_count,
        'network_connection_attempt_count': network.attempts, 'release_adapter_call_count': len(adapter_calls),
        'release_adapter_restored': restored, 'strategy_methods_restored': state['methods_restored']}
    runner._write_json_exclusive(root / 'receipt.json', receipt)


def resolve_sizes(batch, manifest, mapping):
    resolver = batch.load('holding_C_contract_units', Path(manifest['files']['production_portfolio/contract_metadata.py']['path']))
    symbols = sorted(mapping); zero = dict.fromkeys(symbols, 0)
    resolved = resolver.build_resolved_metadata(symbols, zero, zero, zero, mapping, Path(manifest['files']['contract_metadata']['path']))
    if (any(value <= 0 for value in resolved['sizes'].values())
            or set(resolved['metadata_sources'].values()) != {'tqsdk'}):
        raise RuntimeError('holding_full_units_unresolved')
    return resolved['sizes']


def run_parent(summary_sha):
    registry, spec, _ = catalog(summary_sha)
    if OUTPUT.exists():
        raise RuntimeError('holding_full_campaign_already_exists')
    batch, base, runner = configured(summary_sha=summary_sha)
    manifest = runner.build_input_manifest(); runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise RuntimeError('holding_full_disk_reserve')
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'stage': STAGE}, stream)
    paths = None
    try:
        OUTPUT.mkdir(mode=0o700); batch.write_json(OUTPUT / 'input_manifest.json', manifest)
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        root = OUTPUT / 'workers/C'; database = manifest['files']['source_database']
        paths = runner.prepare_stage002_worker_root(root, source_database=Path(database['path']), expected_database_sha256=database['sha256'])
        preflight.write_sandbox_profile(paths['profile'], root)
        command = ['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
            '-I', '-S', '-B', str(Path(__file__).resolve()), '--worker', '--worker-root', str(root),
            '--manifest', str(OUTPUT / 'input_manifest.json'), '--training-summary-sha256', summary_sha]
        with paths['log'].open('wb') as stream:
            result = subprocess.run(command, cwd=paths['runtime'], env=preflight.expected_worker_environment(paths['runtime']),
                                    stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('holding_full_worker_failed:' + str(result.returncode))
        receipt = json.loads(paths['receipt'].read_text()); validate_worker_receipt(receipt, manifest, summary_sha)
        for name, identity in receipt['frames'].items():
            if runner._file_identity(root / (name + '.csv')) != identity:
                raise RuntimeError('holding_full_frame_changed')
        trace = read_trace(root, receipt['trace'])
        if trace['callback_failure'] or trace['execution_failure']:
            raise RuntimeError('holding_full_callback_failure_hidden')
        frames = {name: batch.read_frame(root / (name + '.csv')) for name in FRAME_NAMES}
        equivalence = load('stage007a_runtime_equivalence'); a = equivalence.expected_frames('A0', manifest['formal_identity'])
        batch.validate_daily_calendar(a['daily'], frames['daily'], END)
        reference_receipt = json.loads((batch.REFERENCE / 'receipt.json').read_text())
        if receipt['contract_products'] != reference_receipt['contract_products']:
            raise RuntimeError('holding_full_contract_product_mapping')
        expected_products = set(reference_receipt['contract_products'].values())
        if {row['product_vt_symbol'] for row in trace['states']} != expected_products:
            raise RuntimeError('holding_full_product_inventory')
        observer_audit = load('stage033_holding_observer').qualify_trace(trace['states'], frames['daily'], frames['positions'])
        validator = load('stage049_holding_path_validation')
        books, account_audit = validator.reconcile_account(read_csv(root / 'daily.csv'), read_csv(root / 'positions.csv'),
            read_csv(root / 'trades.csv'), resolve_sizes(batch, manifest, receipt['contract_products']))
        network = preflight.NetworkBlock(); check_guard = inference_guard(preflight, registry, spec, (root,), summary_sha)
        with network, check_guard:
            policy_audit = load('stage047_current_holding_policy').validate_transcript(
                trace['states'], trace['decisions'], books, check_guard.predict_holding)
        if (any(check_guard.counters.values()) or network.attempts
                or policy_audit['decision_count'] != receipt['xgboost_inference']['decision_count']):
            raise RuntimeError('holding_full_prediction_audit_safety')
        calendar = frames['daily'].date.astype(str).str[:10].tolist()
        provider = load('stage046_dynamic_exit_source').DynamicExitSource(manifest['files'], paths['runtime'] / '.vntrader/database.db', calendar)
        action_audit = validator.validate_actions(trace['decisions'], trace['gate'], read_csv(root / 'trades.csv'),
                                                  provider, calendar, trace['states'], trace['terminal'])
        provider.verify_used_inputs()
        if provider.receipt() != trace['source_receipt'] or provider.windows != trace['source_windows']:
            raise RuntimeError('holding_full_execution_source_recalculation')
        if action_audit['exit_count'] != policy_audit['exit_count']:
            raise RuntimeError('holding_full_action_count')
        if action_audit['first_exit_date']:
            prefix = load('stage039_exit_controls').prefix; day = action_audit['first_exit_date']
            equivalence.require_frame_equivalence({key: prefix(value, day) for key, value in a.items()},
                                                  {key: prefix(value, day) for key, value in frames.items()})
        else:
            equivalence.require_frame_equivalence(a, frames)
        a_metrics = base.equity_metrics(a['daily'], a['trades']); c_metrics = base.equity_metrics(frames['daily'], frames['trades'])
        if c_metrics != receipt['metrics']:
            raise RuntimeError('holding_full_metrics_mismatch')
        archiver = batch.load('holding_full_archiver', batch.V4 / 'tools/stage006_prefix_equivalence.py')
        archives = {name: archiver.archive_csv(root / (name + '.csv'), identity) for name, identity in receipt['frames'].items()}
        batch.write_json(root / 'archive_receipt.json', archives)
        for name, identity in archives.items():
            load('stage005_label_collection').verify_archive(root / (name + '.csv.gz'), identity)
        runner.validate_current_input_manifest(manifest)
        summary = {'stage': STAGE, 'status': 'passed', 'A_metrics': a_metrics, 'C_metrics': c_metrics,
            'comparison': load('stage009_path_validation').primary_comparison(a_metrics, c_metrics),
            'observer_audit': observer_audit, 'account_audit': account_audit, 'policy_audit': policy_audit,
            'action_audit': action_audit, 'execution_source': provider.receipt(),
            'prediction_recalculation': check_guard.xgboost_receipt(), 'formal_replay_call_count': 1,
            'historical_model_fit_count': 0, 'reviewer_started': False, 'training_summary_sha256': summary_sha,
            'receipt_sha256': batch.digest(paths['receipt']), 'file_contract_sha256': manifest['file_contract_sha256']}
        batch.write_json(OUTPUT / 'summary.json', summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / 'failure.json').exists():
            batch.write_json(OUTPUT / 'failure.json', {'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
        raise
    finally:
        if paths and paths['runtime'].exists():
            shutil.rmtree(paths['runtime'])
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(); mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true'); mode.add_argument('--run', action='store_true')
    mode.add_argument('--worker', action='store_true'); parser.add_argument('--worker-root', type=Path)
    parser.add_argument('--manifest', type=Path); parser.add_argument('--training-summary-sha256', required=True)
    args = parser.parse_args()
    if args.freeze:
        freeze_inputs(args.training_summary_sha256)
    elif args.worker:
        try:
            run_worker(args)
        except BaseException as exc:
            if args.worker_root and args.worker_root.is_dir():
                load('stage004_label_batch').write_json(args.worker_root / 'worker_failure.json',
                    {'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
            raise
    else:
        run_parent(args.training_summary_sha256)


if __name__ == '__main__':
    main()
