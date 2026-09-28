import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(path):
    return {"path": str(path.resolve()), "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True))


@pytest.fixture
def campaign(tmp_path):
    monthly = load("catalog_monthly", ROOT / "tools/stage006_monthly_models.py")
    spec = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())
    root = tmp_path / "stage006_monthly_fit"
    root.mkdir()
    source = tmp_path / "source.txt"
    source.write_text("synthetic campaign only")
    months = monthly.month_schedule(spec)
    index = {}
    for cutoff in months:
        bundle = {"cutoff": cutoff, "status": "untrained", "train_count": 0, "train_event_ids": [],
                  "train_frame_sha256": "a"*64, "spec_sha256": monthly.spec_digest(spec),
                  "max_train_decision": None, "max_train_end": None, "heads": {}, "fit_count": 0}
        sha = monthly.save_bundle(bundle, root / "models" / cutoff, spec)
        index[cutoff] = {"metadata_sha256": sha, "status": "untrained", "train_count": 0,
                         "fit_count": 0, "train_frame_sha256": "a"*64}
    manifest = {"source_identities": {str(source): identity(source)}, "versions": spec["versions"],
                "months": months, "spec": spec, "dataset_identity": {"snapshot_sha256": "b"*64},
                "historical_evidence_type": spec["historical_evidence_type"]}
    write_json(root / "input_manifest.json", manifest)
    write_json(root / "model_index.json", index)
    (root / "baseline_event_predictions.csv").write_text("synthetic\n")
    summary = {"stage": "stage006_monthly_fit", "status": "passed", "month_count": 80,
               "trained_month_count": 0, "historical_model_fit_count": 0, "baseline_prediction_count": 276,
               "saved_prediction_mismatch_count": 0, "new_strategy_replay_count": 0,
               "network_attempt_count": 0, "historical_evidence_type": spec["historical_evidence_type"],
               "output_identities": {name: identity(root / name) for name in
                    ("input_manifest.json", "model_index.json", "baseline_event_predictions.csv")}}
    write_json(root / "summary.json", summary)
    module = load("catalog_implementation", ROOT / "tools/stage008_model_catalog.py")
    return module, root, spec, source


def rebind(root, name):
    summary = json.loads((root / "summary.json").read_text())
    summary["output_identities"][name] = identity(root / name)
    write_json(root / "summary.json", summary)


def test_complete_catalog_binds_all_months_without_fitting(campaign):
    module, root, spec, _ = campaign
    registry, loaded_spec, evidence = module.load_catalog(root, spec)
    assert len(registry) == 80
    assert loaded_spec == spec
    assert registry["2026-08-01"]["root"] == root / "models/2026-08-01"
    assert evidence["model_file_count"] == 0
    assert evidence["metadata_count"] == 80
    assert evidence["summary_sha256"] == identity(root / "summary.json")["sha256"]


@pytest.mark.parametrize("target", ["source", "metadata", "summary_status", "missing_month", "future_training", "wrong_count", "spec_drift", "path_escape"])
def test_catalog_rejects_incomplete_or_changed_campaign(campaign, target):
    module, root, spec, source = campaign
    if target == "source":
        source.write_text("changed")
    elif target == "metadata":
        (root / "models/2020-01-01/metadata.json").write_text("{}")
    elif target in {"summary_status", "wrong_count"}:
        summary = json.loads((root / "summary.json").read_text())
        summary["status" if target == "summary_status" else "baseline_prediction_count"] = "failed" if target == "summary_status" else 93
        write_json(root / "summary.json", summary)
    elif target == "missing_month":
        index = json.loads((root / "model_index.json").read_text())
        del index["2020-02-01"]
        write_json(root / "model_index.json", index)
        rebind(root, "model_index.json")
    elif target == "future_training":
        path = root / "models/2020-01-01/metadata.json"
        meta = json.loads(path.read_text())
        meta["max_train_end"] = "2020-01-01"
        write_json(path, meta)
        index = json.loads((root / "model_index.json").read_text())
        index["2020-01-01"]["metadata_sha256"] = identity(path)["sha256"]
        write_json(root / "model_index.json", index)
        rebind(root, "model_index.json")
    elif target == "spec_drift":
        spec["estimator"]["max_depth"] = 3
    else:
        summary = json.loads((root / "summary.json").read_text())
        summary["output_identities"]["model_index.json"] = identity(source)
        write_json(root / "summary.json", summary)
    with pytest.raises(RuntimeError):
        module.load_catalog(root, spec)


def test_current_incomplete_history_has_no_model_catalog(tmp_path):
    module = load("catalog_missing", ROOT / "tools/stage008_model_catalog.py")
    spec = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())
    with pytest.raises((RuntimeError, FileNotFoundError)):
        module.load_catalog(tmp_path / "not_trained", spec)
    assert not (tmp_path / "not_trained").exists()


@pytest.mark.parametrize("tampered", [False, True])
def test_catalog_binds_native_model_and_constant_head(campaign, tampered):
    import numpy as np
    import pandas as pd
    import shutil

    module, root, spec, _ = campaign
    monthly = load("catalog_native_monthly", ROOT / "tools/stage006_monthly_models.py")
    x = np.arange(60, dtype=float)
    data = pd.DataFrame({name:x/60 for name in spec["features"]}).assign(
        event_id=[f"synthetic-{i}" for i in range(60)], decision_date="2020-01-01",
        label_end_date="2020-01-02", label_status="verified", lifecycle_status="mature",
        product_vt_symbol="sp.SHFE", return_marginal=-1.0, drawdown_marginal=-2-x/100)
    cutoff = "2026-08-01"
    bundle = monthly.fit_month(data, cutoff, spec)
    directory = root / "models" / cutoff
    shutil.rmtree(directory)
    sha = monthly.save_bundle(bundle, directory, spec)
    index = json.loads((root / "model_index.json").read_text())
    index[cutoff] = {"metadata_sha256":sha,"status":"trained","train_count":60,
                     "fit_count":1,"train_frame_sha256":bundle["train_frame_sha256"]}
    write_json(root / "model_index.json", index)
    summary = json.loads((root / "summary.json").read_text())
    summary.update(trained_month_count=1,historical_model_fit_count=1)
    write_json(root / "summary.json", summary)
    rebind(root, "model_index.json")
    model_path = directory / "drawdown_marginal.ubj"
    if tampered:
        with model_path.open("ab") as stream:
            stream.write(b"tampered")
        with pytest.raises(RuntimeError,match="native_model_changed"):
            module.load_catalog(root,spec)
    else:
        registry, _, evidence = module.load_catalog(root,spec)
        assert evidence["model_file_count"] == 1
        assert model_path in evidence["files"]
        loaded = monthly.load_bundle(registry[cutoff]["root"],registry[cutoff]["metadata_sha256"],spec)
        assert loaded["heads"]["return_marginal"]["kind"] == "constant"
        assert loaded["heads"]["return_marginal"]["mean"] == -1.0
