from datetime import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage049_holding_full_replay.py'
SHA = '1' * 64


def module(name='stage049_holding_full_replay', folder='tools'):
    path = ROOT / folder / (name + '.py')
    assert path.exists(), 'full holding replay is not implemented'
    spec = importlib.util.spec_from_file_location('full049_test_' + name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_cold_bootstrap_configuration_does_not_load_site_dependencies():
    module()
    code = 'import runpy,sys; m=runpy.run_path(' + repr(str(TOOL)) + '); m["configured"](123, ' + repr(SHA) + '); assert not ({"numpy","xgboost","vnpy","pandas"} & set(sys.modules))'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('method', ['freeze_inputs', 'run_parent'])
def test_missing_training_rejected_before_output_or_freeze(tmp_path, monkeypatch, method):
    m = module(); m.MODEL_OUTPUT = tmp_path / 'missing'
    m.FREEZE = tmp_path / 'freeze.json'; m.OUTPUT = tmp_path / 'C'
    with pytest.raises(RuntimeError, match='not_complete'):
        getattr(m, method)(SHA)
    assert not m.OUTPUT.exists() and not m.FREEZE.exists()


@pytest.mark.parametrize('sha', ['', 'auto', '1' * 63, 'G' * 64, None])
def test_training_summary_hash_must_be_explicit(sha):
    with pytest.raises(RuntimeError, match='summary_sha'):
        module().catalog(sha)


@pytest.mark.parametrize('field,value', [('arm', 'A'), ('formal_replay_call_count', 0),
    ('formal_replay_call_count', 2), ('network_connection_attempt_count', 1),
    ('release_adapter_restored', False), ('strategy_methods_restored', False), ('training_summary_sha256', '2' * 64),
    ('sensitive_counters', {'model_fit_count': 1}), ('baseline_inference', {'load_count': 2})])
def test_worker_receipt_enforces_frozen_replay_scope(field, value):
    m = module(); manifest = {'file_contract_sha256': 'frozen', 'formal_identity': {'release': 'fixed'}}
    receipt = {'stage': m.STAGE, 'status': 'passed', 'arm': 'C', 'file_contract_sha256': 'frozen',
        'formal_identity': manifest['formal_identity'], 'formal_replay_call_count': 1, 'network_connection_attempt_count': 0,
        'release_adapter_call_count': 1, 'release_adapter_restored': True, 'strategy_methods_restored': True,
        'training_summary_sha256': SHA, 'sensitive_counters': {'model_fit_count': 0},
        'baseline_inference': {'load_count': 1}, 'frames': dict.fromkeys(m.FRAME_NAMES)}
    m.validate_worker_receipt(receipt, manifest, SHA)
    receipt[field] = value
    with pytest.raises(RuntimeError, match='receipt'):
        m.validate_worker_receipt(receipt, manifest, SHA)


def prepared():
    from vnpy.trader.constant import Direction, Offset

    fixture = module('test_stage039_scoped_exit', 'tests')
    strategy = fixture.Strategy(); engine = strategy.strategy_engine
    engine.trades['BACKTESTING.1'] = SimpleNamespace(tradeid='1', vt_tradeid='BACKTESTING.1',
        vt_symbol='jm2005.DCE', direction=Direction.LONG, offset=Offset.OPEN, price=100., volume=2.)
    def predict(day, product, features):
        return {'cutoff': day[:8] + '01', 'status': 'predicted', 'exit': True,
                'return_marginal': -.1, 'drawdown_marginal': -.1}
    def provider(intent, day):
        return {'price': 112., 'first_time': '2020-01-10T21:00:00', 'fill_date': day, 'source': 'fixture'}
    return fixture, strategy, SimpleNamespace(predict_holding=predict), provider


def test_installed_policy_captures_post_action_terminal_state_and_restores():
    m = module(); f, strategy, guard, provider = prepared()
    originals = f.Strategy.on_bars, f.Strategy.update_trade, f.Engine._resolve_trade_price
    with m.install_holding(f.Strategy, f.Engine, guard, provider) as state:
        assert strategy.on_bars(strategy.strategy_engine.bars) == 'original_result'
        assert len(state['policy'].decisions) == len(state['gate']['intents']) == 1
        assert state['terminal']['states'][0]['actual_positions'] == {'jm2005.DCE': 2.}
        assert state['terminal']['states'][0]['targets'] == {}
        assert state['terminal']['pending_close_volumes'] == {'jm2005.DCE': 2.}
    assert state['gate']['unfilled_order_ids'] == ['BACKTESTING.40']
    assert state['methods_restored'] is True and state['callback_failure'] is None
    assert (f.Strategy.on_bars, f.Strategy.update_trade, f.Engine._resolve_trade_price) == originals


def test_prediction_exception_is_recorded_even_if_engine_catches_it():
    m = module(); f, strategy, guard, provider = prepared()
    def fail(*args):
        raise RuntimeError('prediction marker')
    guard.predict_holding = fail
    with m.install_holding(f.Strategy, f.Engine, guard, provider) as state:
        with pytest.raises(RuntimeError, match='marker'):
            strategy.on_bars(strategy.strategy_engine.bars)
        assert 'prediction marker' in state['callback_failure']
    assert state['methods_restored']


def test_execution_exception_is_recorded_and_does_not_change_fill():
    m = module(); f, strategy, guard, provider = prepared()
    def fail(*args):
        raise RuntimeError('execution marker')
    with m.install_holding(f.Strategy, f.Engine, guard, fail) as state:
        strategy.on_bars(strategy.strategy_engine.bars)
        engine = strategy.strategy_engine; engine.datetime = datetime(2020, 1, 13)
        with pytest.raises(RuntimeError, match='marker'):
            engine._resolve_trade_price(engine.active_limit_orders['BACKTESTING.40'], None)
        assert 'execution marker' in state['execution_failure'] and strategy.get_pos('jm2005.DCE') == 2


def test_trace_verifies_compressed_and_decoded_bytes(tmp_path):
    m = module(); raw = json.dumps({'states': [], 'decisions': []}).encode()
    compressed = gzip.compress(raw, mtime=0); path = tmp_path / 'holding_trace.json.gz'; path.write_bytes(compressed)
    expected = {'file': {'path': str(path), 'size': len(compressed), 'mtime_ns': path.stat().st_mtime_ns,
        'sha256': hashlib.sha256(compressed).hexdigest()}, 'raw_sha256': hashlib.sha256(raw).hexdigest()}
    assert m.read_trace(tmp_path, expected) == json.loads(raw)
    path.write_bytes(gzip.compress(raw + b' ', mtime=0))
    with pytest.raises(RuntimeError, match='trace'):
        m.read_trace(tmp_path, expected)


def test_collection_binds_every_direct_local_dependency(monkeypatch):
    import ast

    m = module(); current = m.load('stage042_holding_labels')
    _, prior = current.adapted().configured()
    monkeypatch.setattr(prior, 'validate_frozen_input_contract', lambda *args: None)
    monkeypatch.setattr(prior, 'validate_current_input_manifest', lambda *args: None)
    monkeypatch.setattr(current, 'adapted', lambda: SimpleNamespace(configured=lambda: (None, prior)))
    monkeypatch.setattr(m, 'catalog', lambda sha: ({}, {}, {'files': []}))
    monkeypatch.setattr(m.load('stage044_holding_training'), 'check_versions', lambda spec: None)
    files = m.collect_inputs(SHA); paths = {value.resolve() for value in files.values()}
    sources = [TOOL, *[ROOT / 'tools' / (name + '.py') for name in
        ('stage045_holding_inference', 'stage045_holding_catalog', 'stage044_holding_models')]]
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'load'
                    and node.args and isinstance(node.args[0], ast.Constant)):
                assert ROOT / 'tools' / (node.args[0].value + '.py') in paths
    assert all(path.is_file() for path in paths)


def test_real_frozen_account_is_accepted_without_replay():
    m = module(); batch = m.load('stage004_label_batch')
    manifest = json.loads((ROOT / 'artifacts/stage042_holding_labels/input_manifest.json').read_text())
    receipt = json.loads((batch.REFERENCE / 'receipt.json').read_text())
    books, audit = m.load('stage049_holding_path_validation').reconcile_account(
        m.read_csv(batch.REFERENCE / 'daily.csv'), m.read_csv(batch.REFERENCE / 'positions.csv'),
        m.read_csv(batch.REFERENCE / 'trades.csv'), m.resolve_sizes(batch, manifest, receipt['contract_products']))
    assert len(books) == 1614 and min(books) == m.START and max(books) == m.END
    assert audit['max_account_daily_error'] <= 1e-7
    assert audit['max_equity_conservation_error'] <= 1e-6


def test_cold_os_registered_native_prediction_drives_original_close(tmp_path):
    fixture = module('test_stage045_holding_inference', 'tests')
    setup = fixture.setup.__wrapped__(tmp_path)
    p = setup['preflight']; paths = p.prepare_worker_root(tmp_path / 'cold_holding')
    p.write_sandbox_profile(paths['profile'], paths['worker_root'])
    registry = {key: {**value, 'root': str(value['root'])} for key, value in setup['registry'].items()}
    code = '\n'.join([
        'import runpy,sys,json; from pathlib import Path; from types import SimpleNamespace; from datetime import datetime',
        f"m=SimpleNamespace(**runpy.run_path({str(TOOL)!r}))",
        'batch,base,runner=m.configured(123,' + repr(SHA) + ')',
        'p=runner.load_metadata_preflight_module().load_preflight_module()',
        f"p._validate_worker_bootstrap(Path({str(paths['runtime'])!r}))",
        f"p.prove_external_write_denied(Path({str(tmp_path / 'outside_probe')!r}))",
        'sys.path.extend([str(p.python_site_packages()),str(m.WORKSPACE)])',
        f"fixture=runpy.run_path({str(Path(__file__).resolve())!r})",
        "f,strategy,_,provider=fixture['prepared']()",
        'engine=strategy.strategy_engine; engine.datetime=datetime(2020,3,4)',
        "engine.bars['jm2005.DCE'].datetime=engine.datetime",
        "factory=m.load('stage045_holding_inference').holding_guard_class",
        f"guard=factory(p,base.load_stage003())((Path({str(paths['worker_root'])!r}),),registry={registry!r},spec={setup['spec']!r})",
        'guard.assert_no_sensitive_modules_loaded()',
        'network=p.NetworkBlock()',
        'with network,guard:',
        ' with m.install_holding(f.Strategy,f.Engine,guard,provider) as state:',
        "  assert strategy.on_bars(engine.bars)=='original_result'",
        "  assert len(state['gate']['intents'])==1 and strategy.get_pos('jm2005.DCE')==2",
        "  assert strategy.get_target('jm2005.DCE')==0 and state['terminal']['pending_close_volumes']=={'jm2005.DCE':2.}",
        "assert state['methods_restored'] and state['gate']['unfilled_order_ids']==['BACKTESTING.40']",
        'assert not network.attempts and not any(guard.counters.values())',
        "assert guard.formal_replay_call_count==0 and guard.decision_count==1",
        'print(json.dumps(guard.xgboost_receipt()))'])
    result = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(paths['profile']), str(Path(sys.executable).resolve()),
        '-I', '-S', '-B', '-c', code], cwd=paths['runtime'], env=p.expected_worker_environment(paths['runtime']),
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['native_model_load_count'] == 2
    assert not (tmp_path / 'outside_probe').exists()
