import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    runner = ROOT / 'run.py'
    assert runner.exists(), 'standalone stock CLI not implemented'
    return subprocess.run([sys.executable, '-I', str(runner), *args],
                          text=True, capture_output=True, timeout=60)


def test_runtime_is_private_and_futures_modules_are_absent():
    result = cli('runtime')
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    assert Path(info['vnpy_settings']).resolve() == (ROOT / 'runtime/.vntrader').resolve()
    assert info['futures_modules'] == []
    assert info['database_opened'] is False


def test_cli_rejects_missing_snapshot_without_a_fake_result():
    result = cli('backtest', '--snapshot', 'does_not_exist_test')
    assert result.returncode != 0
    assert 'snapshot' in result.stderr.lower()


def test_prepare_and_backtest_entrypoint_produce_auditable_artifacts(tmp_path):
    from examples.stock_backtesting.qmt357.tests.test_strategy import fixture_panel
    frame, dates = fixture_panel()
    source = tmp_path / 'fixture.parquet'
    frame.to_parquet(source, index=False)
    name = 'test_' + uuid.uuid4().hex
    result = cli('prepare', '--source', str(source), '--name', name, '--universe-mode', 'custom')
    assert result.returncode == 0, result.stderr
    result = cli('backtest', '--snapshot', name, '--start', str(dates[59].date()),
                 '--end', str(dates[-1].date()), '--run-id', name)
    assert result.returncode == 0, result.stderr
    output = ROOT / 'outputs' / name
    assert {'manifest.json','summary.json','daily_equity.csv','trades.csv','signals.csv','orders.csv',
            'round_trips.csv','rejections.csv','report.md', 'annual_summary.csv',
            'annual_summary.json'}.issubset(p.name for p in output.iterdir())
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['total_trade_count'] == 2
    assert summary['open_positions'] == 0
    annual = json.loads((output / 'annual_summary.json').read_text())
    assert sum(row['total_trade_count'] for row in annual) == summary['total_trade_count']
    assert annual[-1]['end_equity'] == summary['end_equity']
    manifest = json.loads((output / 'manifest.json').read_text())
    assert manifest['execution_timing'] == 'close_signal_next_open'
    assert manifest['snapshot']['historical_membership_verified'] is False
    assert len(manifest['code_sha256']) >= 6
    assert (output / 'daily_equity.csv').stat().st_size > 100
    # Results are frozen, never silently overwritten on rerun.
    rerun = cli('backtest', '--snapshot', name, '--start', str(dates[59].date()),
                 '--end', str(dates[-1].date()), '--run-id', name)
    assert rerun.returncode != 0


def test_output_path_cannot_escape_stock_tree():
    result = cli('backtest', '--snapshot', 'x', '--run-id', '../futures')
    assert result.returncode != 0
