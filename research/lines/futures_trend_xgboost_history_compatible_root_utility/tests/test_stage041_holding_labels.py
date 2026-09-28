import copy
import csv
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage041_holding_labels.py'


def module():
    assert TOOL.exists(), 'holding label runner missing'
    spec = importlib.util.spec_from_file_location('labels041_test', TOOL)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_configuration_keeps_isolated_bootstrap():
    module()
    code = 'import runpy,sys; m=runpy.run_path(' + repr(str(TOOL)) + '); m["configured"](); assert "numpy" not in sys.modules'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def window_file(tmp_path):
    path = tmp_path / 'windows.csv'
    row = {'date': '2020-01-10', 'product_vt_symbol': 'jm.DCE', 'vt_symbol': 'jm2005.DCE',
           'next_calendar_day': '2020-01-13', 'requested_volume': '2', 'first_volume': '20',
           'first_open': '1213.5', 'first_time': '2020-01-10T21:00:00',
           'status': 'source_proxy_qualified_not_execution'}
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    return path


def test_provider_only_matches_current_intent(tmp_path):
    m = module(); m.WINDOWS = window_file(tmp_path)
    intent = {'decision_date': '2020-01-10', 'vt_symbol': 'jm2005.DCE', 'volume': 2}
    value = m.execution_price(intent, '2020-01-13')
    assert value['price'] == 1213.5 and value['first_time'] == '2020-01-10T21:00:00'
    with pytest.raises(ValueError):
        m.execution_price(intent, '2020-01-14')
    with pytest.raises(ValueError):
        m.execution_price({**intent, 'vt_symbol': 'unknown'}, '2020-01-13')
    with pytest.raises(ValueError):
        m.execution_price({**intent, 'volume': 21}, '2020-01-13')


def test_provider_rejects_duplicate_rows(tmp_path):
    m = module(); m.WINDOWS = window_file(tmp_path)
    lines = m.WINDOWS.read_text().splitlines()
    m.WINDOWS.write_text('\n'.join([*lines, lines[1]]) + '\n')
    with pytest.raises(ValueError):
        m.execution_price({'decision_date': '2020-01-10', 'vt_symbol': 'jm2005.DCE', 'volume': 2}, '2020-01-13')


def test_current_features_and_snapshot_must_match_plan():
    m = module()
    helper = importlib.util.spec_from_file_location('panel_samples', ROOT / 'tests/test_stage040_holding_panel.py')
    fixture = importlib.util.module_from_spec(helper); helper.loader.exec_module(fixture)
    row, book = fixture.sample()
    job = {'snapshot': copy.deepcopy(row), 'inventory': copy.deepcopy(book), 'equity_peak': 150000,
           'features': m.load('stage040_holding_panel').visible_features(row, book, 150000)}
    assert m.check_observation(job, row, book, 150000) == job['features']
    row['layers'][0]['entry_price'] = 98
    with pytest.raises(ValueError):
        m.check_observation(job, row, book, 150000)


def test_inputs_bind_panel_spec_and_controls():
    m = module(); files = m.collect_inputs()
    assert files['holding_label_panel_model_spec.json'].name == 'model_spec.json'
    assert files['holding_label_panel_jobs.json'].name == 'jobs.json'
    assert files['holding_label_gate'].name == 'stage039_scoped_exit.py'


def test_parent_manifest_can_load_base_without_a_selected_job(monkeypatch):
    m = module(); sentinel = object()
    base = SimpleNamespace(); runner = SimpleNamespace(load_v1_runner=lambda: sentinel)
    monkeypatch.setattr(m, 'load', lambda name: SimpleNamespace(configured=lambda: (base, runner)))
    monkeypatch.setattr(m, 'collect_inputs', lambda: {})
    _, configured = m.configured()
    assert configured.load_v1_runner() is sentinel
