"""Public contracts: variant identity, independent runtime and frozen outputs."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tarfile
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / 'qmt357'


def cli(*args):
    runner = ROOT / 'run.py'
    assert runner.exists(), 'Commit-specific standalone CLI is not implemented'
    return subprocess.run([sys.executable, '-I', str(runner), *args],
                          text=True, capture_output=True, timeout=60)


def test_runtime_does_not_reuse_baseline_or_futures_settings():
    result = cli('runtime')
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    assert Path(info['vnpy_settings']).resolve() == (ROOT / 'runtime/.vntrader').resolve()
    assert info['futures_modules'] == []
    assert info['database_opened'] is False


def test_commit_defaults_affect_actual_fills_and_frozen_manifest(tmp_path):
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    frame, dates = fixture_panel()
    source = tmp_path / 'fixture.parquet'
    frame.to_parquet(source, index=False)
    name = 'test_commit_' + uuid.uuid4().hex
    prepared = subprocess.run([sys.executable, '-I', str(BASE / 'run.py'), 'prepare',
        '--source', str(source), '--name', name, '--universe-mode', 'custom'],
        text=True, capture_output=True, timeout=60)
    assert prepared.returncode == 0, prepared.stderr
    args = ('backtest', '--snapshot', name, '--start', str(dates[59].date()),
        '--end', str(dates[-1].date()), '--run-id', name, '--commission-rate', '0',
        '--minimum-commission', '0', '--stamp-duty-rate', '0', '--slippage-per-share', '0')
    result = cli(*args)
    assert result.returncode == 0, result.stderr
    output = ROOT / 'outputs' / name
    summary = json.loads((output / 'summary.json').read_text())
    # 32% of 300k permits 900 shares at next-open 104; 45% TP does not
    # close at 120 as the old 12% TP did. Last mark=119, equity=313500.
    assert summary['total_trade_count'] == 1
    assert summary['open_positions'] == 1
    assert summary['end_equity'] == 313500
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['status'] == 'COMPLETE'
    assert manifest['complete_period_result'] is True
    identity = json.loads((output / 'run_identity.json').read_text())
    assert identity['status'] == 'RUNNING'
    assert identity['run_id'] == name
    assert manifest['run_identity_sha256'] == hashlib.sha256((output / 'run_identity.json').read_bytes()).hexdigest()
    assert manifest['settings']['max_positions'] == 3
    assert manifest['settings']['day_position_size'] == .9
    assert manifest['settings']['position_size'] == .32
    assert manifest['settings']['stop_loss_pct'] == .02
    assert manifest['settings']['stop_profit_pct'] == .45
    assert manifest['source_provenance']['commit'] == '4ac255ece55671bb74962f23b5d7fae22fa377e7'
    assert manifest['execution_timing'] == 'close_signal_next_open'
    assert manifest['baseline_code_sha256'] and manifest['code_sha256']
    assert (output / 'trailing_stops.csv').is_file()
    assert (output / 'code_snapshot.tar.gz').is_file()
    annual = json.loads((output / 'annual_summary.json').read_text())
    assert annual[-1]['end_equity'] == 313500
    assert not (BASE / 'outputs' / name).exists()
    assert cli(*args).returncode != 0  # Never overwrite a frozen result.


def test_output_escape_is_rejected_before_loading_data():
    result = cli('backtest', '--snapshot', 'missing', '--run-id', '../futures')
    assert result.returncode != 0
    assert 'run-id' in result.stderr


def test_snapshot_escape_is_rejected():
    result = cli('backtest', '--snapshot', '../foreign')
    assert result.returncode != 0
    assert 'snapshot' in result.stderr.lower()


def test_held_factor_failure_keeps_pre_execution_identity_without_performance(tmp_path):
    # Moving identity creation after engine.run_backtesting would lose this real
    # failure, while disabling the held-action guard would wrongly publish stats.
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    frame, dates = fixture_panel()
    frame.loc[(frame.vt_symbol == '600000.SSE') & (frame.date == dates[-1]), 'adj_factor'] = 2.
    source = tmp_path / 'held_factor_failure.parquet'
    frame.to_parquet(source, index=False)
    name = 'test_commit_failed_' + uuid.uuid4().hex
    prepared = subprocess.run([sys.executable, '-I', str(BASE / 'run.py'), 'prepare',
        '--source', str(source), '--name', name, '--universe-mode', 'custom'],
        text=True, capture_output=True, timeout=60)
    assert prepared.returncode == 0, prepared.stderr
    args = ('backtest', '--snapshot', name, '--start', str(dates[59].date()),
            '--end', str(dates[-1].date()), '--run-id', name)
    result = cli(*args)
    assert result.returncode != 0
    assert 'Unexplained corporate action' in result.stderr
    output = ROOT / 'outputs' / name
    assert (output / 'manifest.json').is_file(), 'Failed replay lost its frozen execution identity'
    manifest = json.loads((output / 'manifest.json').read_text())
    identity = json.loads((output / 'run_identity.json').read_text())
    assert manifest['status'] == 'FAILED'
    assert manifest['complete_period_result'] is False
    assert manifest['failure']['type'] == 'ValueError'
    assert '600000.SSE' in manifest['failure']['message']
    assert manifest['failure']['failure_date'] == str(dates[-1].date())
    assert manifest['failure']['last_completed_date'] == str(dates[60].date())
    assert manifest['failure']['processed_trades'] == 1
    assert manifest['failure']['completed_sessions'] == 2
    assert manifest['failure']['open_positions'] == 1
    assert identity['status'] == 'RUNNING'
    assert identity['snapshot']['panel_sha256'] == hashlib.sha256((BASE / 'data' / name / 'panel.parquet').read_bytes()).hexdigest()
    assert identity['settings']['max_positions'] == 3
    assert identity['settings']['day_position_size'] == .9
    assert identity['code_sha256']['run.py'] == hashlib.sha256((ROOT / 'run.py').read_bytes()).hexdigest()
    assert manifest['run_identity_sha256'] == hashlib.sha256((output / 'run_identity.json').read_bytes()).hexdigest()
    archive = output / 'code_snapshot.tar.gz'
    assert identity['code_archive_sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive, 'r:gz') as frozen:
        content = frozen.extractfile('qmt357_commit4ac255e/run.py').read()
        assert hashlib.sha256(content).hexdigest() == identity['code_sha256']['run.py']
    for filename in ('summary.json', 'annual_summary.json', 'annual_summary.csv', 'report.md', 'daily_equity.csv'):
        assert not (output / filename).exists(), f'Failed replay published performance: {filename}'
    frozen_files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    assert cli(*args).returncode != 0
    assert frozen_files == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}


def test_variant_snapshot_and_baseline_snapshot_are_mutually_exclusive():
    result = cli('backtest', '--snapshot', 'base', '--variant-snapshot', 'variant')
    assert result.returncode != 0
    assert 'not allowed with argument' in result.stderr


def test_variant_snapshot_escape_is_rejected_by_its_own_loader():
    result = cli('backtest', '--variant-snapshot', '../foreign')
    assert result.returncode != 0
    assert 'single safe directory name' in result.stderr


def test_variant_cli_consumes_private_snapshot_without_baseline_copy(tmp_path):
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    from examples.stock_backtesting.qmt357_commit4ac255e.data import prepare_snapshot
    frame, dates = fixture_panel()
    source = tmp_path / 'variant_only.parquet'
    frame.to_parquet(source, index=False)
    name = 'test_private_' + uuid.uuid4().hex
    private_snapshot = prepare_snapshot(source, name, 'custom')
    assert not (BASE / 'data' / name).exists()
    result = cli('backtest', '--variant-snapshot', name, '--run-id', name,
        '--start', str(dates[59].date()), '--end', str(dates[-1].date()))
    assert result.returncode == 0, result.stderr
    manifest = json.loads((ROOT / 'outputs' / name / 'manifest.json').read_text())
    assert manifest['status'] == 'COMPLETE'
    assert manifest['snapshot_scope'] == 'variant_private'
    assert Path(manifest['snapshot_path']).resolve() == private_snapshot.resolve()
    assert manifest['snapshot']['panel_sha256'] == hashlib.sha256((private_snapshot / 'panel.parquet').read_bytes()).hexdigest()
    assert not (BASE / 'outputs' / name).exists()


def test_publication_failure_cleans_performance_temporary_files(tmp_path):
    # A failure between writing JSON and its atomic rename must not expose
    # statistics, even under a temporary filename, for an unsuccessful run.
    from examples.stock_backtesting.qmt357_commit4ac255e.run import _recorded_execution
    code = tmp_path / 'module.py'
    code.write_text('# frozen test source\n')
    target = tmp_path / 'output'
    identity = dict(run_id='publication-failure', status='RUNNING', complete_period_result=False)
    with pytest.raises(RuntimeError, match='publication interrupted'):
        with _recorded_execution(target, identity, {code: code.read_bytes()}, tmp_path):
            # Identity/archive must exist BEFORE the consumer executes anything.
            assert (target / 'code_snapshot.tar.gz').is_file()
            assert json.loads((target / 'manifest.json').read_text())['status'] == 'RUNNING'
            assert (target / 'run_identity.json').is_file()
            for name in ('summary.json', 'annual_summary.json'):
                (target / name).write_text('{"not_a_complete_result": true}')
                (target / (name + '.tmp')).write_text('{"not_a_complete_result": true}')
            raise RuntimeError('publication interrupted')
    manifest = json.loads((target / 'manifest.json').read_text())
    assert manifest['status'] == 'FAILED'
    assert manifest['failure']['last_completed_date'] is None
    assert manifest['failure']['processed_trades'] == 0
    for name in ('summary.json', 'annual_summary.json'):
        assert not (target / name).exists()
        assert not (target / (name + '.tmp')).exists()


def test_complete_manifest_write_failure_cannot_leave_performance(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from examples.stock_backtesting.qmt357_commit4ac255e import run
    code = tmp_path / 'module.py'
    code.write_text('# source\n')
    target = tmp_path / 'output'
    original_write = run._write_json
    def failing_final_write(path, value):
        if path.name == 'manifest.json' and value.get('status') == 'COMPLETE':
            raise OSError('simulated final write failure')
        original_write(path, value)
    monkeypatch.setattr(run, '_write_json', failing_final_write)
    with pytest.raises(OSError, match='final write failure'):
        with run._recorded_execution(target, {'status':'RUNNING'},
                                     {code:code.read_bytes()}, tmp_path) as state:
            state['engine'] = SimpleNamespace(rejections=[])
            (target/'summary.json').write_text('{"pnl":123}')
    assert json.loads((target/'manifest.json').read_text())['status'] == 'FAILED'
    assert (target/'failure.json').exists()
    assert not (target/'summary.json').exists()


def test_known_unsupported_restructuring_rejects_even_explicit_vendor_split(tmp_path):
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    from examples.stock_backtesting.qmt357_commit4ac255e.data import prepare_snapshot
    frame, dates = fixture_panel()
    event = frame.vt_symbol.eq('600000.SSE') & frame.date.eq(dates[-1])
    frame.loc[event, 'adj_factor'] = 2.
    frame['split_ratio'] = 1.
    frame.loc[event, 'split_ratio'] = 2.
    frame.attrs['unsupported_corporate_actions'] = [dict(vt_symbol='600000.SSE',
        date=str(dates[-1].date()),reason='Issuer allocation is not the vendor total-capital split')]
    source = tmp_path/'unsupported.parquet'
    frame.to_parquet(source,index=False)
    name = 'test_unsupported_' + uuid.uuid4().hex
    prepare_snapshot(source,name,'custom')
    result = cli('backtest','--variant-snapshot',name,'--run-id',name,
        '--start',str(dates[59].date()),'--end',str(dates[-1].date()))
    assert result.returncode != 0, 'Known invalid vendor split must not be executed'
    manifest = json.loads((ROOT/'outputs'/name/'manifest.json').read_text())
    assert manifest['status'] == 'FAILED'
    assert 'Unsupported corporate action' in manifest['failure']['message']
    assert not (ROOT/'outputs'/name/'summary.json').exists()
