import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage042_holding_labels.py'


def module():
    assert TOOL.exists(), 'resumable canonical label runner missing'
    spec = importlib.util.spec_from_file_location('test_labels042', TOOL)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_inherited_ids_are_exactly_completed_not_pending():
    m = module(); ids = m.inherited_ids()
    assert len(ids) == 14 and m.CANARY not in ids
    assert m.CANARY == '513f85cf5e472350c12c3e644cc631ad1d668c6ba09a078bb84ecbd22cdbc3ea'


def test_selection_retains_full_plan_and_time_order():
    m = module(); jobs = [{'observation_id': k} for k in ['a', 'b', m.CANARY, 'd']]
    assert m.select_jobs(jobs, {'a','b'}, 'canary', 1) == [jobs[2]]
    assert m.select_jobs(jobs, {'a','b',m.CANARY}, 'next', 5) == [jobs[3]]
    with pytest.raises(ValueError): m.select_jobs(jobs, {'a'}, 'next', 3)
    with pytest.raises(ValueError): m.select_jobs(jobs, {'x'}, 'canary', 3)


def test_bootstrap_boundary_and_canonical_module_wiring():
    module()
    code = ('import runpy,sys; d=runpy.run_path(' + repr(str(TOOL)) + '); m=d["adapted"](); m.configured(); '
        'assert "numpy" not in sys.modules; assert m.STAGE=="stage042_holding_labels"; '
        'gate=m.load("stage039_scoped_exit"); assert gate.current_inventory.__module__.endswith("stage042_canonical_inventory")')
    result = subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_inputs_bind_old_labels_archives_and_failure():
    m = module(); files = m.collect_inputs()
    assert files['canonical_inventory'].name == 'stage042_canonical_inventory.py'
    assert files['inherited_collection_summary'].name == 'summary.json'
    assert len([k for k in files if k.startswith('inherited_archive/')]) == 98
    assert any(p.name=='exit_audit.json' and m.CANARY in str(p) for p in files.values())
