import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage039_exit_controls.py'


def module():
    assert TOOL.exists(), 'exit controls missing'
    spec = importlib.util.spec_from_file_location('test_controls039', TOOL)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_first_fixed_control_is_selected_by_identity_not_pnl():
    m = module(); row = m.target_window()
    assert (row['date'], row['product_vt_symbol'], row['vt_symbol']) == ('2020-01-10', 'jm.DCE', 'jm2005.DCE')
    assert row['next_calendar_day'] == '2020-01-13' and float(row['actual_volume']) == 2


@pytest.mark.parametrize('control', ['A0', 'E'])
def test_worker_configuration_preserves_bootstrap_import_boundary(control):
    module()
    code = 'import runpy,sys; m=runpy.run_path(' + repr(str(TOOL)) + '); m["configured"](' + repr(control) + '); assert "numpy" not in sys.modules'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_control_inputs_include_raw_source_freeze_and_new_implementation():
    m = module(); files = m.collect_inputs()
    assert sum(key.startswith('execution_raw/') for key in files) == 341
    assert files['exit_gate'].name == 'stage039_scoped_exit.py'
    assert files['exit_parent_summary'].name == 'summary.json'
    assert all(str(path).startswith('/') for path in files.values())
