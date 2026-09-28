from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_TOOL = ROOT / "tools/stage002_event_feature_qualification.py"
PRODUCTION = Path("/Users/bytedance/Desktop/person/vnpy_production_live/examples/portfolio_backtesting")
MODEL = PRODUCTION / "backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_selection_pairwise_v2_risk_weighted.joblib"
MODEL_SUMMARY = PRODUCTION / "backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_summary_selection_pairwise_v2_risk_weighted.json"
MODEL_SHA = "ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66"
SUMMARY_SHA = "c399a5787577c1cb55276766ed28b0cad8385c063de5b492076dfa8e0619ee86"
RUNTIME_SOURCE = PRODUCTION / "qmt_roll_ai_selection_pairwise_runtime.py"
STAGE = "stage003_frozen_baseline_event_qualification"
INPUT_COUNT = 1469


def _load_base():
    spec = importlib.util.spec_from_file_location("v4_stage003_base", BASE_TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_input_files():
    files = _load_base().collect_input_files()
    failure = ROOT / "artifacts/stage002_event_feature_qualification_failed"
    files.update({
        "v4_stage003_runner": Path(__file__).resolve(),
        "v4_stage003_tests": ROOT / "tests/test_stage003_frozen_baseline_event_qualification.py",
        "v4_stage003_preregistration": ROOT / "stages/20260905_1913_stage003_frozen_baseline_inference_preregistration.md",
        "v4_stage002_failure_record": ROOT / "stages/20260905_1913_stage002_failed_baseline_model_import.md",
        "v4_stage002_failure": failure / "failure.json",
        "v4_stage002_worker_failure": failure / "workers/A1/failure_receipt.json",
        "v4_stage002_failed_manifest": failure / "input_manifest.json",
        "v4_stage002_claim": ROOT / "stages/20260905_stage002_execution_state/claim.json",
        "v4_stage002_freeze": ROOT / "stages/20260905_stage002a_input_contract_freeze.json",
        "frozen_baseline_model": MODEL,
        "frozen_baseline_model_summary": MODEL_SUMMARY,
    })
    if len(files) != INPUT_COUNT or any(p.is_symlink() or not p.is_file() for p in files.values()):
        raise RuntimeError("stage003_inventory_invalid")
    if sha256(MODEL) != MODEL_SHA or sha256(MODEL_SUMMARY) != SUMMARY_SHA:
        raise RuntimeError("frozen_baseline_artifact_changed")
    return dict(sorted(files.items()))


def baseline_guard_class(preflight):
    class FrozenBaselineGuard(preflight.SensitiveOperationGuard):
        _forbidden_import_prefixes = tuple(
            name for name in preflight.SensitiveOperationGuard._forbidden_import_prefixes
            if name != "sklearn"
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.model = None
            self.estimator_ids = set()
            self.load_count = 0
            self.inference_calls = {}
            self.original_load = None

        def _load_frozen(self, filename, *args, **kwargs):
            if not isinstance(filename, (str, Path)) or Path(filename).resolve() != MODEL.resolve():
                self._block("sensitive_module_import_count", "unregistered_model_load")
            if self.load_count or sha256(MODEL) != MODEL_SHA:
                self._block("sensitive_module_import_count", "frozen_model_identity_or_load_count")
            model = self.original_load(filename, *args, **kwargs)
            signature = [(name, type(step).__module__, type(step).__name__) for name, step in model.steps]
            if type(model).__module__ != "sklearn.pipeline" or signature != [
                ("scaler", "sklearn.preprocessing._data", "StandardScaler"),
                ("classifier", "sklearn.linear_model._logistic", "LogisticRegression"),
            ] or model.n_features_in_ != 19:
                self._block("sensitive_module_import_count", "frozen_model_shape_changed")
            self.model = model
            self.estimator_ids = {id(model), *(id(step) for _, step in model.steps)}
            self.load_count += 1
            return model

        def _trusted_inference(self, frame):
            if id(frame.f_locals.get("self")) not in self.estimator_ids:
                return False
            caller = frame.f_back
            while caller is not None:
                if caller.f_code.co_name == "_predict_daily_scores" and (
                    caller.f_globals.get("__name__") == "qmt_roll_ai_selection_pairwise_runtime"
                    and Path(caller.f_code.co_filename).resolve() == RUNTIME_SOURCE.resolve()
                ):
                    runtime = caller.f_locals.get("self")
                    return getattr(runtime, "model", None) is self.model and (
                        Path(runtime.model_path).resolve() == MODEL.resolve()
                    )
                caller = caller.f_back
            return False

        def _profile(self, frame, event, argument):
            if event == "call" and not self._blocking:
                module = str(frame.f_globals.get("__name__", ""))
                function = frame.f_code.co_name
                if module.startswith("sklearn"):
                    if function in {"fit", "fit_transform", "fit_predict", "partial_fit"} or function.endswith("_fit"):
                        self._block("model_fit_count", f"model_training_forbidden:{module}.{function}")
                    if function in {"predict", "predict_proba", "predict_log_proba", "decision_function", "transform"}:
                        if not self._trusted_inference(frame):
                            self._block("prediction_count", f"unregistered_model_inference:{module}.{function}")
                        key = f"{module}.{function}"
                        self.inference_calls[key] = self.inference_calls.get(key, 0) + 1
                        return
            super()._profile(frame, event, argument)

        def __enter__(self):
            import joblib

            self.joblib = joblib
            self.original_load = joblib.load
            super().__enter__()
            joblib.load = self._load_frozen
            return self

        def __exit__(self, *args):
            self.joblib.load = self.original_load
            return super().__exit__(*args)

        def receipt(self):
            return {
                "model_sha256": MODEL_SHA,
                "summary_sha256": SUMMARY_SHA,
                "load_count": self.load_count,
                "inference_calls": dict(sorted(self.inference_calls.items())),
            }

    return FrozenBaselineGuard


def run_guarded_extraction(
    *, worker_root, expected_outputs, expected_candidate_module_path, attestation,
    preflight, metadata_preflight, v1, feature_module, context_importer=None,
):
    base = _load_base()
    importer = context_importer or preflight.import_production_context_with_attestation
    network = preflight.NetworkBlock()
    guard = baseline_guard_class(preflight)((worker_root,), allowed_formal_replay_count=1)
    guard.assert_no_sensitive_modules_loaded()
    with network, guard:
        context, calls, restored = importer(attestation)
        features, formal, evidence = base.extract_formal_event_features(
            context, worker_root=worker_root, expected_outputs=expected_outputs,
            expected_candidate_module_path=expected_candidate_module_path,
            v1=v1, feature_module=feature_module, metadata_preflight=metadata_preflight,
        )
    baseline = guard.receipt()
    if (network.attempts or any(guard.counters.values()) or guard.formal_replay_call_count != 1
            or len(calls) != 1 or restored is not True or baseline["load_count"] != 1):
        raise RuntimeError("stage003_safety_contract_failed")
    evidence["frozen_baseline_inference"] = baseline
    return features, formal, {
        "sensitive_counters": dict(guard.counters),
        "network_connection_attempt_count": network.attempts,
        "formal_replay_call_count": guard.formal_replay_call_count,
        "release_adapter_call_count": len(calls),
        "release_adapter_calls": list(calls),
        "release_adapter_restored": restored,
        "metadata_preflight": evidence,
    }


def load_runner():
    runner = _load_base().load_runner()
    runner.__file__ = str(Path(__file__).resolve())
    runner.STAGE = STAGE
    runner.EXPECTED_INPUT_FILE_COUNT = INPUT_COUNT
    runner.EXECUTION_STATE_DIR = ROOT / "stages/20260905_stage003_execution_state"
    runner.CLAIM_PATH = runner.EXECUTION_STATE_DIR / "claim.json"
    runner.INPUT_FREEZE_PATH = ROOT / "stages/20260905_stage003a_input_contract_freeze.json"
    runner.FINAL_DIR = ROOT / "artifacts" / STAGE
    runner.FAILURE_DIR = ROOT / "artifacts" / f"{STAGE}_failed"
    runner.collect_input_files = collect_input_files
    runner.run_guarded_extraction = run_guarded_extraction
    original_portable = runner.portable_metadata_evidence

    def portable(evidence):
        result = original_portable(evidence)
        baseline = evidence["frozen_baseline_inference"]
        if baseline["load_count"] != 1 or baseline["model_sha256"] != MODEL_SHA or baseline["summary_sha256"] != SUMMARY_SHA:
            raise RuntimeError("baseline_receipt_invalid")
        result["frozen_baseline_inference"] = baseline
        return result

    runner.portable_metadata_evidence = portable
    return runner


if __name__ == "__main__":
    raise SystemExit(load_runner().main())
