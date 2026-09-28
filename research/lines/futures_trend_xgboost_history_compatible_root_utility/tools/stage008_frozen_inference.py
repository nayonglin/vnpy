from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAIN_FUNCTIONS = {"fit", "fit_transform", "fit_predict", "partial_fit", "train", "cv", "update", "boost", "boost_one_iter"}
PREDICT_FUNCTIONS = {"predict", "predict_proba", "inplace_predict", "apply"}
MUTATE_FUNCTIONS = {"load_model", "load_config", "set_param", "set_params", "set_attr", "__setstate__"}
NATIVE_TRAIN = ("XGBoosterUpdateOneIter", "XGBoosterTrainOneIter", "XGBoosterTrainOneIterWithSplitGrad")
NATIVE_WRITE = ("XGBoosterSaveModel", "XGDMatrixSaveBinary")
NATIVE_MUTATE = ("XGBoosterLoadModel", "XGBoosterLoadModelFromBuffer", "XGBoosterUnserializeFromBuffer",
                 "XGBoosterLoadJsonConfig", "XGBoosterSetParam", "XGBoosterSetAttr")
NATIVE_PREDICT = ("XGBoosterPredictFromDMatrix", "XGBoosterPredictFromDense", "XGBoosterPredictFromColumnar",
                  "XGBoosterPredictFromCSR", "XGBoosterPredictFromCudaArray", "XGBoosterPredictFromCudaColumnar")


def frozen_guard_class(preflight, baseline, monthly):
    parent = baseline.baseline_guard_class(preflight)

    class FrozenMonthlyGuard(parent):
        _forbidden_import_prefixes = tuple(name for name in parent._forbidden_import_prefixes if name != "xgboost")

        def __init__(self, *args, registry, spec, **kwargs):
            super().__init__(*args, **kwargs)
            self.spec = json.loads(json.dumps(spec))
            self.registry = {}
            for cutoff, entry in registry.items():
                monthly.validate_cutoff(cutoff)
                root = Path(entry["root"])
                if root.is_symlink() or not root.is_dir() or root.name != cutoff:
                    raise RuntimeError("registered_model_directory_invalid")
                self.registry[cutoff] = {"root": root.resolve(), "metadata_sha256": entry["metadata_sha256"]}
            self.bundles = {}
            self.xgb_ids = {}
            self.xgb_handles = {}
            self.prediction_calls = {}
            self.native_model_load_count = 0
            self.decision_count = 0
            self._loading = None
            self._predicting = None
            self._active = False
            self._native_originals = {}

        def _check_open(self, file, mode):
            path = self._resolve_path(file)
            if path is not None and not any(token in str(mode) for token in ("w", "a", "x", "+")):
                forbidden = (ROOT / "artifacts/stage004_label_batch/jobs", ROOT / "artifacts/stage005_label_collection")
                if any(root == path or root in path.parents for root in forbidden):
                    self._block("label_value_read_count", "replay_label_directory_read_forbidden")
            super()._check_open(file, mode)

        def _in_load(self):
            return self._loading is not None and self._loading[1] == threading.get_ident()

        def _in_prediction(self):
            return self._predicting is not None and self._predicting[1] == threading.get_ident()

        def _profile(self, frame, event, argument):
            if event == "call" and not self._blocking:
                module = str(frame.f_globals.get("__name__", ""))
                function = frame.f_code.co_name
                if module.startswith("xgboost"):
                    if function in TRAIN_FUNCTIONS or function.endswith("_fit"):
                        self._block("model_fit_count", f"xgboost_training_forbidden:{function}")
                    if function in PREDICT_FUNCTIONS:
                        if (not self._in_prediction()
                                or id(frame.f_locals.get("self")) not in self.xgb_ids[self._predicting[0]]):
                            self._block("prediction_count", "unregistered_xgboost_prediction")
                        key = f"{module}.{function}"
                        self.prediction_calls[key] = self.prediction_calls.get(key, 0) + 1
                        return
                    if function in MUTATE_FUNCTIONS:
                        if not self._in_load() or function == "__setstate__":
                            self._block("sensitive_module_import_count", "xgboost_model_mutation_forbidden")
                        if function == "load_model":
                            value = frame.f_locals.get("fname")
                            if not isinstance(value, (str, Path)) or Path(value).resolve() not in self._loading[2]:
                                self._block("sensitive_module_import_count", "unregistered_xgboost_model_load")
                        return
                    if function in {"save_model", "save_binary"}:
                        self._block("production_file_write_count", "xgboost_model_write_forbidden")
            super()._profile(frame, event, argument)

        def _native_wrapper(self, name, original):
            def invoke(*args):
                if name in NATIVE_TRAIN:
                    self._block("model_fit_count", f"xgboost_native_training_forbidden:{name}")
                if name in NATIVE_WRITE:
                    self._block("production_file_write_count", f"xgboost_native_write_forbidden:{name}")
                if name in NATIVE_MUTATE:
                    if (not self._in_load() or name in {"XGBoosterLoadModelFromBuffer", "XGBoosterUnserializeFromBuffer"}):
                        self._block("sensitive_module_import_count", "xgboost_native_mutation_forbidden")
                    if name == "XGBoosterLoadModel":
                        filename = args[1].value.decode()
                        if Path(filename).resolve() not in self._loading[2]:
                            self._block("sensitive_module_import_count", "unregistered_native_model_load")
                        self.native_model_load_count += 1
                if name in NATIVE_PREDICT:
                    if (not self._in_prediction()
                            or getattr(args[0], "value", None) not in self.xgb_handles[self._predicting[0]]):
                        self._block("prediction_count", "unregistered_native_prediction")
                return original(*args)
            return invoke

        def _load_month(self, cutoff):
            if cutoff not in self.registry:
                raise RuntimeError("month_not_registered")
            entry = self.registry[cutoff]
            root = entry["root"]
            if monthly.digest(root / "metadata.json") != entry["metadata_sha256"]:
                raise RuntimeError("model_metadata_changed")
            meta = json.loads((root / "metadata.json").read_text())
            if meta["cutoff"] != cutoff:
                raise RuntimeError("registered_model_month_mismatch")
            paths = {root / f"{name}.ubj" for name, head in meta["heads"].items() if head["kind"] == "xgboost"}
            if any(path.is_symlink() for path in paths):
                raise RuntimeError("registered_model_symlink")
            self._loading = (cutoff, threading.get_ident(), paths)
            try:
                bundle = monthly.load_bundle(root, entry["metadata_sha256"], self.spec)
                estimators = [head["estimator"] for head in bundle["heads"].values() if head["estimator"] is not None]
                boosters = [estimator.get_booster() for estimator in estimators]
                self.xgb_ids[cutoff] = {id(item) for item in [*estimators, *boosters]}
                self.xgb_handles[cutoff] = {item.handle.value for item in boosters}
                self.bundles[cutoff] = bundle
            finally:
                self._loading = None

        def predict_event(self, event):
            if not self._active or self._blocking or self._predicting is not None:
                raise RuntimeError("inference_guard_not_ready")
            cutoff = date.fromisoformat(event["decision_date"]).replace(day=1).isoformat()
            product = event["product_vt_symbol"]
            if product == "fu.SHFE":
                return monthly.predict_decision(None, event["decision_date"], product, event, self.spec)
            if cutoff not in self.bundles:
                self._load_month(cutoff)
            self._predicting = (cutoff, threading.get_ident())
            try:
                result = monthly.predict_decision(self.bundles[cutoff], event["decision_date"], product, event, self.spec)
                self.decision_count += 1
                return result
            finally:
                self._predicting = None

        def __enter__(self):
            import xgboost

            if self._active:
                raise RuntimeError("inference_guard_already_active")
            self._lib = xgboost.core._LIB
            super().__enter__()
            try:
                for name in (*NATIVE_TRAIN, *NATIVE_WRITE, *NATIVE_MUTATE, *NATIVE_PREDICT):
                    original = getattr(self._lib, name)
                    self._native_originals[name] = original
                    setattr(self._lib, name, self._native_wrapper(name, original))
                self._active = True
                return self
            except BaseException:
                self.__exit__(None, None, None)
                raise

        def __exit__(self, *args):
            for name, original in self._native_originals.items():
                setattr(self._lib, name, original)
            self._native_originals.clear()
            self._active = False
            return super().__exit__(*args)

        def xgboost_receipt(self):
            return {"loaded_months": sorted(self.bundles), "native_model_load_count": self.native_model_load_count,
                    "decision_count": self.decision_count, "prediction_calls": dict(sorted(self.prediction_calls.items())),
                    "metadata_sha256": {cutoff: self.registry[cutoff]["metadata_sha256"] for cutoff in sorted(self.bundles)}}

    return FrozenMonthlyGuard
