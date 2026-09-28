import importlib.util
import json
import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def setup(tmp_path):
    monthly = load("guard_monthly", ROOT / "tools/stage006_monthly_models.py")
    baseline = load("guard_baseline", ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage003_frozen_baseline_event_qualification.py")
    spec = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())
    x = np.arange(60, dtype=float)
    data = pd.DataFrame({name: x / 60 for name in spec["features"]})
    data = data.assign(event_id=[f"synthetic-{i}" for i in range(60)], decision_date="2020-01-01",
                       label_end_date="2020-01-02", label_status="verified", lifecycle_status="mature",
                       product_vt_symbol="sp.SHFE", return_marginal=-1-x/100, drawdown_marginal=-2-x/100)
    bundle = monthly.fit_month(data, "2020-03-01", spec)
    directory = tmp_path / "models/2020-03-01"
    sha = monthly.save_bundle(bundle, directory, spec)
    early = monthly.fit_month(data, "2020-01-01", spec)
    early_path = tmp_path / "models/2020-01-01"
    early_sha = monthly.save_bundle(early, early_path, spec)
    registry = {"2020-03-01": {"root": directory, "metadata_sha256": sha},
                "2020-01-01": {"root": early_path, "metadata_sha256": early_sha}}
    event = {name: 0.2 for name in spec["features"]}
    event.update(decision_date="2020-03-04", product_vt_symbol="sp.SHFE")
    module = load("guard_implementation", ROOT / "tools/stage008_frozen_inference.py")
    preflight = baseline.load_runner().load_metadata_preflight_module().load_preflight_module()
    cls = module.frozen_guard_class(preflight, baseline, monthly)
    guard = cls((tmp_path,), registry=registry, spec=spec)
    return module, monthly, baseline, preflight, guard, event, bundle, directory


def test_registered_prediction_matches_native_roundtrip_and_loads_each_month_once(setup):
    _, monthly, _, preflight, guard, event, original, _ = setup
    expected = monthly.predict_decision(original, event["decision_date"], event["product_vt_symbol"], event, guard.spec)
    with preflight.NetworkBlock(), guard:
        assert guard.predict_event(event) == expected
        assert guard.predict_event(event) == expected
    receipt = guard.xgboost_receipt()
    assert receipt["loaded_months"] == ["2020-03-01"]
    assert receipt["native_model_load_count"] == 2
    assert receipt["decision_count"] == 2
    assert receipt["prediction_calls"]["xgboost.sklearn.predict"] == 4
    assert receipt["prediction_calls"]["xgboost.core.inplace_predict"] == 4
    assert not any(guard.counters.values())
    assert expected["skip"] is True


def test_untrained_and_fu_do_not_load_xgboost(setup):
    _, _, _, preflight, guard, event, _, _ = setup
    with preflight.NetworkBlock(), guard:
        assert guard.predict_event({**event, "decision_date": "2020-01-15"})["status"] == "untrained"
        assert guard.predict_event({**event, "product_vt_symbol": "fu.SHFE"})["status"] == "fixed_fu"
    assert guard.xgboost_receipt()["native_model_load_count"] == 0


def test_missing_month_cannot_silently_fallback_to_previous_model(setup):
    _, _, _, _, guard, event, _, _ = setup
    with pytest.raises(RuntimeError, match="month_not_registered"):
        with guard:
            guard.predict_event({**event, "decision_date": "2020-04-01"})


@pytest.mark.parametrize("name", ["metadata.json", "return_marginal.ubj"])
def test_changed_registered_files_are_rejected_before_prediction(setup, name):
    _, _, _, _, guard, event, _, directory = setup
    with (directory / name).open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(RuntimeError, match="changed"):
        with guard:
            guard.predict_event(event)


@pytest.mark.parametrize("operation", ["fit", "update", "train", "direct_predict", "other_load", "set_param", "native_train", "native_save"])
def test_training_mutation_or_unregistered_prediction_is_denied(setup, operation, tmp_path):
    import xgboost as xgb

    _, _, _, preflight, guard, event, original, directory = setup
    features = pd.DataFrame([{name: event[name] for name in guard.spec["features"]}])
    matrix = xgb.DMatrix(features, label=[0])
    with pytest.raises(preflight.ImportPreflightError):
        with guard:
            guard.predict_event(event)
            estimator = guard.bundles["2020-03-01"]["heads"]["return_marginal"]["estimator"]
            if operation == "fit":
                estimator.fit(features, [0])
            elif operation == "update":
                estimator.get_booster().update(matrix, 0)
            elif operation == "train":
                xgb.train({}, matrix, num_boost_round=1)
            elif operation == "direct_predict":
                estimator.predict(features)
            elif operation == "other_load":
                xgb.XGBRegressor().load_model(directory / "return_marginal.ubj")
            elif operation == "set_param":
                estimator.get_booster().set_param({"base_score": 10})
            elif operation == "native_train":
                xgb.core._LIB.XGBoosterUpdateOneIter(None, 0, None)
            else:
                xgb.core._LIB.XGBoosterSaveModel(None, b"forbidden.ubj")
    assert sum(guard.counters.values()) == 1
    assert not (tmp_path / "forbidden.ubj").exists()


@pytest.mark.parametrize("operation", ["network", "ctp", "outside_write", "label_read", "lr_predict"])
def test_existing_network_broker_filesystem_and_lr_gates_remain(setup, operation, tmp_path):
    import joblib

    module, _, baseline, preflight, guard, event, _, _ = setup
    outside = tmp_path.parent / "stage008_forbidden.txt"
    with pytest.raises(preflight.ImportPreflightError):
        with preflight.NetworkBlock(), guard:
            guard.predict_event(event)
            if operation == "network":
                socket.create_connection(("example.com", 443))
            elif operation == "ctp":
                __import__("vnpy_ctp")
            elif operation == "outside_write":
                outside.write_text("forbidden")
            elif operation == "label_read":
                (module.ROOT / "artifacts/stage005_label_collection/20260905_213655_918111/events.csv").read_text()
            else:
                model = joblib.load(baseline.MODEL)
                model.predict_proba([[0] * 19])
    assert not outside.exists()


def test_native_entrypoints_and_profile_are_restored_on_failure(setup):
    import sys
    import xgboost as xgb

    _, _, _, preflight, guard, event, _, _ = setup
    native = xgb.core._LIB.XGBoosterUpdateOneIter
    profile = sys.getprofile()
    with pytest.raises(preflight.ImportPreflightError):
        with guard:
            guard.predict_event(event)
            xgb.core._LIB.XGBoosterUpdateOneIter(None, 0, None)
    assert xgb.core._LIB.XGBoosterUpdateOneIter is native
    assert sys.getprofile() is profile


def test_fresh_os_sandbox_can_load_and_predict_without_preimported_dependencies(setup, tmp_path):
    import subprocess
    import sys

    _, _, baseline, preflight, guard, event, _, _ = setup
    paths = preflight.prepare_worker_root(tmp_path / "cold_worker")
    preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
    registry = {key: {"root": str(value["root"]), "metadata_sha256": value["metadata_sha256"]}
                for key, value in guard.registry.items()}
    code = "\n".join([
        "import runpy,sys,json; from pathlib import Path; from types import SimpleNamespace",
        f"baseline=SimpleNamespace(**runpy.run_path({str(Path(baseline.__file__))!r}))",
        "p=baseline.load_runner().load_metadata_preflight_module().load_preflight_module()",
        f"p._validate_worker_bootstrap(Path({str(paths['runtime'])!r}))",
        f"p.prove_external_write_denied(Path({str(tmp_path / 'outside_probe')!r}))",
        "sys.path.extend([str(p.python_site_packages())])",
        f"monthly=SimpleNamespace(**runpy.run_path({str(ROOT / 'tools/stage006_monthly_models.py')!r}))",
        f"factory=runpy.run_path({str(ROOT / 'tools/stage008_frozen_inference.py')!r})['frozen_guard_class']",
        f"guard=factory(p,baseline,monthly)((Path({str(paths['worker_root'])!r}),),registry={registry!r},spec={guard.spec!r})",
        "guard.assert_no_sensitive_modules_loaded()",
        "with p.NetworkBlock(),guard:",
        f" result=guard.predict_event({event!r})",
        "assert result['skip'] is True and guard.decision_count==1 and not any(guard.counters.values())",
        "print(json.dumps(guard.xgboost_receipt()))",
    ])
    result = subprocess.run(["/usr/bin/sandbox-exec","-f",str(paths["profile"]),
                             str(Path(sys.executable).resolve()),"-I","-S","-B","-c",code],
                            cwd=paths["runtime"],env=preflight.expected_worker_environment(paths["runtime"]),
                            capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["native_model_load_count"] == 2
    assert receipt["prediction_calls"]["xgboost.core.inplace_predict"] == 2
    assert not (tmp_path / "outside_probe").exists()
