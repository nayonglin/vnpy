import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/stage003_frozen_baseline_event_qualification.py"


@pytest.fixture
def module():
    spec = importlib.util.spec_from_file_location("v4_stage003_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("operation", ["fit", "predict_proba", "other_load"])
def test_frozen_load_allowed_but_training_unscoped_prediction_and_other_load_denied(module, tmp_path, operation):
    import joblib

    preflight = module.load_runner().load_metadata_preflight_module().load_preflight_module()
    guard = module.baseline_guard_class(preflight)((tmp_path,))
    original = joblib.load
    error = {
        "fit": "model_training_forbidden",
        "predict_proba": "unregistered_model_inference",
        "other_load": "unregistered_model_load",
    }[operation]
    with pytest.raises(preflight.ImportPreflightError, match=error):
        with preflight.NetworkBlock(), guard:
            model = joblib.load(module.MODEL)
            assert guard.load_count == 1
            if operation == "other_load":
                joblib.load(tmp_path / "untrusted.joblib")
            elif operation == "fit":
                model.fit([[0] * 19, [1] * 19], [0, 1])
            else:
                model.predict_proba([[0] * 19])
    assert joblib.load is original


def test_prediction_requires_known_estimator_and_actual_runtime_frame(module, tmp_path):
    preflight = module.load_runner().load_metadata_preflight_module().load_preflight_module()
    guard = module.baseline_guard_class(preflight)((tmp_path,))
    model = object()
    guard.model = model
    guard.estimator_ids = {id(model)}
    caller = SimpleNamespace(
        f_code=SimpleNamespace(co_name="_predict_daily_scores", co_filename=str(module.RUNTIME_SOURCE)),
        f_globals={"__name__": "qmt_roll_ai_selection_pairwise_runtime"},
        f_locals={"self": SimpleNamespace(model=model, model_path=module.MODEL)},
        f_back=None,
    )
    frame = SimpleNamespace(f_locals={"self": model}, f_back=caller)
    assert guard._trusted_inference(frame)
    frame.f_locals["self"] = object()
    assert not guard._trusted_inference(frame)
    frame.f_locals["self"] = model
    caller.f_code.co_filename = str(tmp_path / "other.py")
    assert not guard._trusted_inference(frame)


def test_stage003_inputs_bind_baseline_and_failed_attempt(module, tmp_path):
    runner = module.load_runner()
    files = runner.collect_input_files()
    assert len(files) == 1469
    assert files["frozen_baseline_model"] == module.MODEL
    assert files["v4_stage002_failure"].is_file()
    assert "stage003" in runner.CLAIM_PATH.parent.name
    assert runner.FINAL_DIR.name == module.STAGE
    assert runner.FAILURE_DIR != ROOT / "artifacts/stage002_event_feature_qualification_failed"
