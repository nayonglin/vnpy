import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/stage009_full_path_replay.py"


def module():
    assert TOOL.exists(), "full path runner implementation missing"
    spec = importlib.util.spec_from_file_location("full_path_runner_test", TOOL)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_worker_bootstrap_does_not_import_site_dependencies():
    module()
    code = "import runpy,sys; m=runpy.run_path(" + repr(str(TOOL)) + "); m['configured'](123); assert 'numpy' not in sys.modules and 'xgboost' not in sys.modules"
    result = subprocess.run([sys.executable,"-I","-S","-B","-c",code],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_missing_full_training_cannot_freeze_or_start_replay(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m,"MODEL_OUTPUT",tmp_path / "missing_models")
    monkeypatch.setattr(m,"FREEZE",tmp_path / "freeze.json")
    monkeypatch.setattr(m,"OUTPUT",tmp_path / "C")
    with pytest.raises(RuntimeError,match="not_complete"):
        m.freeze_inputs()
    assert not m.FREEZE.exists()
    assert not m.OUTPUT.exists()


@pytest.mark.parametrize("field,value", [("arm","A0"),("formal_replay_call_count",2),
                                          ("network_connection_attempt_count",1),("release_adapter_restored",False)])
def test_receipt_gate_rejects_wrong_execution_scope(field,value):
    m = module()
    manifest = {"file_contract_sha256":"frozen", "formal_identity":{"release":"fixed"}}
    receipt = {"stage":m.STAGE,"status":"passed","arm":"C","file_contract_sha256":"frozen",
               "formal_identity":manifest["formal_identity"],"formal_replay_call_count":1,
               "network_connection_attempt_count":0,"sensitive_counters":{"model_fit_count":0},
               "baseline_inference":{"load_count":1},"release_adapter_call_count":1,"release_adapter_restored":True,
               "frames":dict.fromkeys(m.FRAME_NAMES),"audit":{"source_sha256":"source"},
               "xgboost_inference":{"decision_count":2}}
    m.validate_worker_receipt(receipt,manifest,"source")
    receipt[field] = value
    with pytest.raises(RuntimeError,match="receipt"):
        m.validate_worker_receipt(receipt,manifest,"source")


def test_equivalence_gate_rechecks_receipts_and_compressed_outputs(tmp_path):
    import json
    import shutil

    m = module()
    source = ROOT / "artifacts/stage007a_runtime_equivalence"
    qualified = m.qualify_equivalence(source)
    assert len(qualified["files"]) == 20
    assert qualified["decoded_archive_count"] == 14
    changed = tmp_path / "changed_equivalence"
    shutil.copytree(source, changed)
    receipt = changed / "workers/A0/receipt.json"
    content = json.loads(receipt.read_text())
    content["audit"]["skip_count"] = 1
    receipt.write_text(json.dumps(content))
    with pytest.raises(RuntimeError,match="equivalence_receipt_changed"):
        m.qualify_equivalence(changed)
