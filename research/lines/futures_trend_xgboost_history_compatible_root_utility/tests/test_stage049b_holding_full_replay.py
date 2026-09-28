import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage049b_holding_full_replay.py'
SHA = '69e4e9bd8dab96be26288ea51a76fca5cc834c773a92b0408dbf957b63b71a5a'


def module():
    assert TOOL.exists(), 'freeze compatibility adapter is not implemented'
    spec = importlib.util.spec_from_file_location('test_holding049b', TOOL)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_new_freeze_passes_real_schema_and_old_failure_is_preserved(tmp_path):
    b = module(); m = b.adapted(); _, _, runner = m.configured(123, SHA)
    old = json.loads(b.PRIOR_FREEZE.read_text())
    manifest = {**old, 'stage': m.STAGE, 'input_file_count': 123}
    with pytest.raises(Exception, match='schema_invalid'):
        runner.validate_frozen_input_contract(b.PRIOR_FREEZE, manifest)
    freeze = tmp_path / 'freeze.json'; freeze.write_text(json.dumps(b.freeze_payload(manifest)))
    payload = runner.validate_frozen_input_contract(freeze, manifest)
    assert len(payload) == 8 and 'training_summary_sha256' not in payload
    assert old['training_summary_sha256'] == SHA
    m.FREEZE = freeze
    assert m.configured(summary_sha=SHA)[2].EXPECTED_INPUT_FILE_COUNT == 123


@pytest.mark.parametrize('sha', ['2' * 64, '', None])
def test_model_cannot_change_when_freeze_does_not_have_extra_field(sha):
    with pytest.raises(RuntimeError, match='fixed_training_summary_changed'):
        module().adapted().configured(123, sha)


def test_scientific_functions_stay_in_original_module_and_worker_uses_adapter():
    m = module().adapted()
    assert Path(m.__file__) == TOOL
    assert m.OUTPUT.name == m.STAGE == 'stage049b_holding_full_replay'
    assert m.FREEZE.name == 'stage049b_input_freeze.json'
    for name in ('install_holding', 'run_worker', 'run_parent', 'validate_worker_receipt', 'read_trace', 'resolve_sizes'):
        assert Path(inspect.unwrap(getattr(m, name)).__code__.co_filename).name == 'stage049_holding_full_replay.py'


def test_cold_bootstrap_is_site_free():
    module()
    code = 'import runpy,sys; m=runpy.run_path(' + repr(str(TOOL)) + ')["adapted"](); m.configured(123,' + repr(SHA) + '); assert not ({"numpy","xgboost","vnpy","pandas"} & set(sys.modules))'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_new_input_contract_binds_prior_failure_adapter_and_scientific_contract(monkeypatch):
    b = module(); m = b.adapted(); current = m.load('stage042_holding_labels')
    _, prior = current.adapted().configured()
    monkeypatch.setattr(prior, 'validate_frozen_input_contract', lambda *args: None)
    monkeypatch.setattr(prior, 'validate_current_input_manifest', lambda *args: None)
    monkeypatch.setattr(current, 'adapted', lambda: type('Stub', (), {'configured': staticmethod(lambda: (None, prior))}))
    monkeypatch.setattr(m, 'catalog', lambda sha: ({}, {}, {'files': []}))
    monkeypatch.setattr(m.load('stage044_holding_training'), 'check_versions', lambda spec: None)
    paths = set(m.collect_inputs(SHA).values())
    assert {TOOL, Path(__file__), b.CONTRACT, b.PRIOR_FREEZE, b.SCIENTIFIC_CONTRACT}.issubset(paths)
    assert all(path.is_file() for path in paths)
