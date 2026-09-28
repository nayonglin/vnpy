from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage004_frozen_xgboost_fusion.py"
)
SPEC = importlib.util.spec_from_file_location(
    "stage004_frozen_xgboost_fusion", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
stage004 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage004
SPEC.loader.exec_module(stage004)


def test_technical_gates_require_stage003_parity_and_xgb_determinism() -> None:
    summary = {
        "input_identity_stable": True,
        "feature_count": 108,
        "valid_fold_count": 8,
        "oos_months": 47,
        "pit_violation_rows": 0,
        "a_prediction_max_abs_diff": 0.0,
        "xgb_repeat_prediction_max_abs_diff": 0.0,
        "xgb_repeat_dump_sha_match": True,
        "xgb_probabilities_valid": True,
        "monthly_arm_rows": 141,
        "sealed_holdout_rows_read": 0,
    }

    assert all(stage004.build_technical_gates(summary).values())
    summary["a_prediction_max_abs_diff"] = 1e-8
    assert not stage004.build_technical_gates(summary)["stage003_a_prediction_exact"]


def test_publish_refuses_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "stage004"
    output.mkdir()

    with pytest.raises(stage004.Stage004Error, match="output_already_exists"):
        stage004.publish_artifacts(
            output,
            predictions=pd.DataFrame(),
            monthly_metrics=pd.DataFrame(),
            fold_audit=pd.DataFrame(),
            model_dump_audit=pd.DataFrame(),
            summary={},
        )

