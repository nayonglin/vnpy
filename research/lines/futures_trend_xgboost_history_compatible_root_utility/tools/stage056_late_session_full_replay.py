from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA = '9ca987c18819cd0e3ec0f6d56282825f2b0d4b5bea7a0e702d16471c5ab60715'
CONTRACT = ROOT / 'stages/20260907_0748_stage054_056_late_session_consumption_contract.md'


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('late056_' + name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def adapted():
    compatibility = load('stage049b_holding_full_replay')
    compatibility.MODEL_SHA = MODEL_SHA
    module = compatibility.adapted()
    module.STAGE = 'stage056_late_session_full_replay'
    module.OUTPUT = ROOT / 'artifacts' / module.STAGE
    module.FREEZE = ROOT / 'stages/stage056_input_freeze.json'
    module.MODEL_OUTPUT = ROOT / 'artifacts/stage053_late_session_training'
    module.__file__ = str(Path(__file__).resolve())
    original_inputs, original_install, original_load = module.collect_inputs, module.install_holding, module.load

    def catalog(summary_sha):
        if summary_sha != MODEL_SHA:
            raise RuntimeError('late_fixed_training_summary_changed')
        if not module.MODEL_OUTPUT.is_dir():
            raise RuntimeError('late_training_campaign_not_complete')
        spec = json.loads((ROOT / 'artifacts/stage052_late_session_features/candidate_spec.json').read_text())
        jobs = json.loads((module.PANEL / 'jobs.json').read_text())['jobs']
        months = json.loads((module.PANEL / 'monthly_inventory.json').read_text())
        return load('stage054_late_session_consumption').load_catalog(module.MODEL_OUTPUT, spec, summary_sha, jobs, months)

    def collect_inputs(summary_sha):
        files = original_inputs(summary_sha)
        files['late_consumption_contract'] = CONTRACT
        for name in ('stage052_late_session_features', 'stage054_late_session_consumption',
                     'stage055_current_late_session', 'stage056_late_session_full_replay'):
            files['late_tool/' + name] = ROOT / 'tools' / (name + '.py')
            files['late_test/' + name] = ROOT / 'tests' / ('test_' + name + '.py')
        return dict(sorted(files.items()))

    def inference_guard(preflight, registry, spec, roots, summary_sha, allowed_replays=0):
        _, base, _ = module.configured(summary_sha=summary_sha)
        cls = load('stage054_late_session_consumption').holding_guard_class(preflight, base.load_stage003())
        return cls(roots, registry=registry, spec=spec, allowed_formal_replay_count=allowed_replays)

    def select(name):
        if name == 'stage046_dynamic_exit_source':
            return SimpleNamespace(DynamicExitSource=load('stage055_current_late_session').LateSessionSource,
                                   collect_inputs=original_load(name).collect_inputs)
        return original_load(name)

    module.load = select

    @contextmanager
    def install_holding(strategy_class, engine_class, guard, provider):
        policy = load('stage055_current_late_session').bind_policy(provider)
        prior = module.load
        module.load = lambda name: policy if name == 'stage047_current_holding_policy' else prior(name)
        try:
            with original_install(strategy_class, engine_class, guard, provider) as state:
                yield state
        finally:
            module.load = prior

    module.catalog, module.collect_inputs = catalog, collect_inputs
    module.inference_guard, module.install_holding = inference_guard, install_holding
    module.run_parent = lambda summary_sha: run_parent(module, summary_sha)
    return module


def audit_policy(trace, books, provider, network, guard):
    with network, guard as active:
        return load('stage055_current_late_session').bind_policy(provider).validate_transcript(
            trace['states'], trace['decisions'], books, active.predict_holding)


def run_parent(m, summary_sha):
    registry, spec, _ = m.catalog(summary_sha)
    output = m.OUTPUT
    if output.exists():
        raise RuntimeError('holding_full_campaign_already_exists')
    batch, base, runner = m.configured(summary_sha=summary_sha)
    manifest = runner.build_input_manifest(); runner.validate_frozen_input_contract(m.FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise RuntimeError('holding_full_disk_reserve')
    lock = batch.OUTPUT / 'run.lock'
    with lock.open('x') as stream:
        json.dump({'pid': os.getpid(), 'stage': m.STAGE}, stream)
    paths = None
    try:
        output.mkdir(mode=0o700); batch.write_json(output / 'input_manifest.json', manifest)
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        root = output / 'workers/C'; database = manifest['files']['source_database']
        paths = runner.prepare_stage002_worker_root(root, source_database=Path(database['path']), expected_database_sha256=database['sha256'])
        preflight.write_sandbox_profile(paths['profile'], root)
        command = ['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
            '-I', '-S', '-B', str(Path(__file__).resolve()), '--worker', '--worker-root', str(root),
            '--manifest', str(output / 'input_manifest.json'), '--training-summary-sha256', summary_sha]
        with paths['log'].open('wb') as stream:
            result = subprocess.run(command, cwd=paths['runtime'], env=preflight.expected_worker_environment(paths['runtime']),
                                    stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('holding_full_worker_failed:' + str(result.returncode))
        receipt = json.loads(paths['receipt'].read_text()); m.validate_worker_receipt(receipt, manifest, summary_sha)
        for name, identity in receipt['frames'].items():
            if runner._file_identity(root / (name + '.csv')) != identity:
                raise RuntimeError('holding_full_frame_changed')
        trace = m.read_trace(root, receipt['trace'])
        if trace['callback_failure'] or trace['execution_failure']:
            raise RuntimeError('holding_full_callback_failure_hidden')
        frames = {name: batch.read_frame(root / (name + '.csv')) for name in m.FRAME_NAMES}
        equivalence = m.load('stage007a_runtime_equivalence'); a = equivalence.expected_frames('A0', manifest['formal_identity'])
        batch.validate_daily_calendar(a['daily'], frames['daily'], m.END)
        reference_receipt = json.loads((batch.REFERENCE / 'receipt.json').read_text())
        if receipt['contract_products'] != reference_receipt['contract_products']:
            raise RuntimeError('holding_full_contract_product_mapping')
        if {row['product_vt_symbol'] for row in trace['states']} != set(reference_receipt['contract_products'].values()):
            raise RuntimeError('holding_full_product_inventory')
        observer_audit = m.load('stage033_holding_observer').qualify_trace(trace['states'], frames['daily'], frames['positions'])
        validator = m.load('stage049_holding_path_validation')
        books, account_audit = validator.reconcile_account(m.read_csv(root / 'daily.csv'), m.read_csv(root / 'positions.csv'),
            m.read_csv(root / 'trades.csv'), m.resolve_sizes(batch, manifest, receipt['contract_products']))
        calendar = frames['daily'].date.astype(str).str[:10].tolist()
        # Unlike Stage049, the parent source exists before feature audit and is reused for actual exit quotes.
        provider = load('stage055_current_late_session').LateSessionSource(manifest['files'], paths['runtime'] / '.vntrader/database.db', calendar)
        network = preflight.NetworkBlock(); check_guard = m.inference_guard(preflight, registry, spec, (root,), summary_sha)
        policy_audit = audit_policy(trace, books, provider, network, check_guard)
        if (any(check_guard.counters.values()) or network.attempts
                or policy_audit['decision_count'] != receipt['xgboost_inference']['decision_count']
                or policy_audit['decision_count'] != len(provider.feature_records)):
            raise RuntimeError('holding_full_prediction_audit_safety')
        action_audit = validator.validate_actions(trace['decisions'], trace['gate'], m.read_csv(root / 'trades.csv'),
                                                  provider, calendar, trace['states'], trace['terminal'])
        provider.verify_used_inputs()
        if provider.receipt() != trace['source_receipt'] or provider.windows != trace['source_windows']:
            raise RuntimeError('holding_full_execution_source_recalculation')
        if action_audit['exit_count'] != policy_audit['exit_count']:
            raise RuntimeError('holding_full_action_count')
        if action_audit['first_exit_date']:
            prefix = m.load('stage039_exit_controls').prefix; day = action_audit['first_exit_date']
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
            m.load('stage005_label_collection').verify_archive(root / (name + '.csv.gz'), identity)
        runner.validate_current_input_manifest(manifest)
        source_receipt = provider.receipt(); source_receipt.pop('feature_records')
        summary = {'stage': m.STAGE, 'status': 'passed', 'A_metrics': a_metrics, 'C_metrics': c_metrics,
            'comparison': m.load('stage009_path_validation').primary_comparison(a_metrics, c_metrics),
            'observer_audit': observer_audit, 'account_audit': account_audit, 'policy_audit': policy_audit,
            'action_audit': action_audit, 'execution_source': source_receipt, 'feature_count': 11,
            'prediction_recalculation': check_guard.xgboost_receipt(), 'formal_replay_call_count': 1,
            'historical_model_fit_count': 0, 'reviewer_started': False, 'training_summary_sha256': summary_sha,
            'receipt_sha256': batch.digest(paths['receipt']), 'file_contract_sha256': manifest['file_contract_sha256']}
        batch.write_json(output / 'summary.json', summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if output.exists() and not (output / 'failure.json').exists():
            batch.write_json(output / 'failure.json', {'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
        raise
    finally:
        if paths and paths['runtime'].exists():
            shutil.rmtree(paths['runtime'])
        lock.unlink()


if __name__ == '__main__':
    adapted().main()
