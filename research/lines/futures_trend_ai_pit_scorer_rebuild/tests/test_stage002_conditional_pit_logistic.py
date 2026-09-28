from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage002_conditional_pit_logistic.py"
)
SPEC = importlib.util.spec_from_file_location(
    "stage002_conditional_pit_logistic", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_build_technical_gates_maps_frozen_thresholds() -> None:
    summary = {
        "input_identity_stable": True,
        "feature_count": 108,
        "valid_fold_count": 8,
        "oos_months": 47,
        "pit_violation_rows": 0,
        "oos_unlisted_rows": 0,
        "oos_partial_horizon_rows": 0,
        "repeat_prediction_max_abs_diff": 0.0,
        "repeat_model_state_max_abs_diff": 0.0,
        "probabilities_valid": True,
        "minimum_monthly_candidate_count": 14,
        "sealed_holdout_rows_read": 0,
    }

    assert all(runner.build_technical_gates(summary).values())
    summary["valid_fold_count"] = 6
    assert not runner.build_technical_gates(summary)["valid_folds_ge_7"]


def test_publish_refuses_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "stage002"
    output.mkdir()

    with pytest.raises(runner.Stage002Error, match="output_already_exists"):
        runner.publish_artifacts(
            output,
            conditional_samples=pd.DataFrame(),
            fold_audit=pd.DataFrame(),
            predictions=pd.DataFrame(),
            monthly_metrics=pd.DataFrame(),
            model_parameters=pd.DataFrame(),
            summary={},
        )

