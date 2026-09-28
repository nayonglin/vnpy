import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def module():
    spec = importlib.util.spec_from_file_location("stage004b_test", ROOT / "tools/stage004b_frozen_artifact_analysis.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_byte_identical_real_features_pass_original_qualification(module):
    frames = module.load_frames(module.SOURCE / "workers/A")
    upstream = pd.read_csv(module.base.UPSTREAM / "event_features.csv")
    result = module.base.support().evaluate_stage002_features(frames["root_features"], upstream)
    assert result["passed"] is True
    assert result["worker_comparison"]["max_abs_numeric_diff"] == 0


def test_actual_vnpy_enum_root_fill_and_close_are_found(module):
    frames = module.load_frames(module.SOURCE / "workers/A")
    target = module.base.earliest_target()
    receipt = json.loads((module.SOURCE / "workers/A/receipt.json").read_text())
    result = module.base.event_endpoint(frames, target, receipt["contract_products"])
    assert result == {"status": "mature", "event_id": target["event_id"],
                      "first_fill_date": "2022-02-09", "end_date": "2022-03-15"}
