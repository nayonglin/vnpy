import copy
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage041b_numeric_inventory_labels.py'


def module():
    assert TOOL.exists(), 'numeric inventory adapter missing'
    spec = importlib.util.spec_from_file_location('numeric041b_test', TOOL)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_actual_control_numeric_equivalence_without_cost_tolerance():
    m = module(); plan = m.load('stage041_holding_labels').read_plan()
    job = plan['jobs'][0]
    book = copy.deepcopy(job['inventory']); symbol = job['vt_symbol']
    book[symbol]['average_entry_price'] = '1203.0'
    assert m.check_observation(job, job['snapshot'], book, job['equity_peak']) == job['features']
    book[symbol]['average_entry_price'] = '1203.00000000000000000000001'
    with pytest.raises(ValueError):
        m.check_observation(job, job['snapshot'], book, job['equity_peak'])


@pytest.mark.parametrize('field,value', [('quantity', '2.1'), ('average_entry_price', 'NaN'),
    ('source_trade_ids', ['BACKTESTING.2'])])
def test_inventory_differences_still_fail(field, value):
    m = module(); job = m.load('stage041_holding_labels').read_plan()['jobs'][0]
    book = copy.deepcopy(job['inventory']); book[job['vt_symbol']][field] = value
    with pytest.raises(ValueError):
        m.check_observation(job, job['snapshot'], book, job['equity_peak'])


def test_adapter_worker_bootstrap_and_unique_output():
    module()
    code = ('import runpy,sys; m=runpy.run_path(' + repr(str(TOOL)) + '); a=m["adapted"](); a.configured(); '
            'assert "numpy" not in sys.modules; assert a.STAGE=="stage041b_holding_labels"; '
            'assert a.__file__==' + repr(str(TOOL)) + '; assert "stage041_failed_manifest" in a.collect_inputs()')
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
