import copy
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[1] / "tools/stage006b_prefix_artifact_analysis.py"
    spec = importlib.util.spec_from_file_location("stage006b_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records():
    manifest = {"stage": "stage006_prefix_equivalence", "file_contract_sha256": "frozen", "formal_identity": {"capital": 150000}}
    receipt = {"stage": "stage004_counterfactual_validation", "status": "passed", "arm": "S",
        "file_contract_sha256": "frozen", "formal_identity": {"capital": 150000}, "formal_replay_call_count": 1,
        "network_connection_attempt_count": 0, "sensitive_counters": {"model_fit_count": 0},
        "audit": {"skip_count": 1, "verified_snapshot_count": 1}}
    return receipt, manifest


def test_known_component_receipt_requires_current_campaign_identity(module):
    receipt, manifest = records()
    module.verify_receipt(receipt, manifest, "S")
    changed = copy.deepcopy(receipt)
    changed["file_contract_sha256"] = "previous_campaign"
    with pytest.raises(RuntimeError, match="component_receipt"):
        module.verify_receipt(changed, manifest, "S")


@pytest.mark.parametrize("field,value", [("formal_replay_call_count", 2), ("network_connection_attempt_count", 1),
                                         ("stage", "unregistered_component"), ("arm", "A")])
def test_component_compatibility_does_not_relax_safety(module, field, value):
    receipt, manifest = records()
    receipt[field] = value
    with pytest.raises(RuntimeError, match="component_receipt"):
        module.verify_receipt(receipt, manifest, "S")
