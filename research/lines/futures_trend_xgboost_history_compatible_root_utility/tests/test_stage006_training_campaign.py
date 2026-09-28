import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/stage006_training_campaign.py"


def module():
    assert PATH.exists(), "training campaign implementation missing"
    spec = importlib.util.spec_from_file_location("training_campaign_test", PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_real_partial_snapshot_blocks_campaign_without_creating_output(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "OUTPUT", tmp_path / "not-created")
    source = ROOT / "artifacts/stage005_label_collection/20260905_210220_024349/summary.json"
    with pytest.raises(RuntimeError, match="training_inventory_incomplete"):
        m.run_campaign(source)
    assert not m.OUTPUT.exists()


def test_installed_versions_match_frozen_contract():
    spec = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())
    assert module().check_versions(spec) == spec["versions"]


def test_dependency_drift_is_not_silently_upgraded():
    spec = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())
    spec["versions"]["xgboost"] = "0.0.0"
    with pytest.raises(RuntimeError, match="training_dependency_version_changed"):
        module().check_versions(spec)
