import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/stage007a_runtime_equivalence.py"


def module():
    assert PATH.exists(), "runtime equivalence implementation missing"
    spec = importlib.util.spec_from_file_location("runtime_equivalence_test", PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_noop_has_no_fixed_target_but_bridge_is_frozen():
    m = module()
    bridge = m.bridge_job()
    assert bridge["event_id"] == "0b6b77b1582778490a948bf6ffb47151ccee3302eec9d1ba9688ef906edd31fe"
    assert bridge["target"]["decision_date"] == "2022-02-08" and bridge["end_date"] == "2022-03-15"


def test_worker_input_inventory_contains_only_six_added_inputs():
    m = module()
    assert len(m.collect_inputs()) == m.INPUT_COUNT == 1517


def test_worker_bootstrap_does_not_import_numpy():
    import subprocess
    import sys
    code = "import runpy,sys; m=runpy.run_path(" + repr(str(PATH)) + "); m['configured']('A0'); assert 'numpy' not in sys.modules"
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_equivalence_requires_every_column_and_value():
    import pandas as pd
    m = module()
    expected = {"daily": pd.DataFrame({"equity": [150000.0]})}
    changed = {"daily": pd.DataFrame({"equity": [149999.0]})}
    with pytest.raises(AssertionError):
        m.require_frame_equivalence(expected, changed)
