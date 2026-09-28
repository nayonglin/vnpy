from __future__ import annotations

import importlib.util
import json
import os
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage015_macro_training"
OUTPUT = ROOT / "artifacts" / STAGE
MACRO_OUTPUT = ROOT / "artifacts/stage014_macro_features"
SNAPSHOT = ROOT / "artifacts/stage005_label_collection/20260906_020434_393264/summary.json"
CONTRACT = ROOT / "stages/20260906_0348_stage015_016_macro_candidate_contract.md"
ID_COLUMNS = ["event_id", "candidate_index", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]


def load(name):
    spec = importlib.util.spec_from_file_location("macro_" + name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def macro():
    return load("stage014_macro_features")


def join_features(data, features, oldspec, spec):
    import numpy as np
    import pandas as pd

    m = macro()
    if spec != m.candidate_spec(oldspec):
        raise RuntimeError("macro_training_spec_changed")
    if (set(features.columns) != set(ID_COLUMNS + ["source_date"] + m.FEATURES)
            or set(m.FEATURES) & set(data.columns)
            or data.event_id.isna().any() or data.event_id.duplicated().any()
            or features.event_id.isna().any() or features.event_id.duplicated().any()
            or len(data) != len(features) or set(data.event_id) != set(features.event_id)):
        raise RuntimeError("macro_training_event_inventory_invalid")
    ordered = features.set_index("event_id").loc[data.event_id].reset_index()
    if not ordered[ID_COLUMNS].equals(data[ID_COLUMNS].reset_index(drop=True)):
        raise RuntimeError("macro_training_event_identity_mismatch")
    m.validate_dates(ordered.source_date)
    m.validate_dates(ordered.decision_date)
    if not ordered.source_date.lt(ordered.decision_date).all():
        raise RuntimeError("macro_training_source_not_past")
    if not np.isfinite(ordered[m.FEATURES].to_numpy(dtype=float)).all():
        raise RuntimeError("macro_training_features_nonfinite")
    result = data.copy(deep=True)
    for name in m.FEATURES:
        result[name] = ordered[name].to_numpy(copy=True)
    pd.testing.assert_frame_equal(result[data.columns], data, check_exact=True)
    return result


def load_dataset():
    import pandas as pd

    m = macro()
    path = MACRO_OUTPUT / "summary.json"
    if m.identity(path)["sha256"] != "60be4114f96f5eb147bb9b05e2c0eb042038dab7312100b1ef34429443c4595e":
        raise RuntimeError("macro_training_source_summary_changed")
    summary = json.loads(path.read_text())
    if summary["status"] != "features_qualified_no_models":
        raise RuntimeError("macro_training_features_not_qualified")
    files = json.loads((MACRO_OUTPUT / "input_manifest.json").read_text())
    files.update({str(MACRO_OUTPUT / name): item for name, item in summary["outputs"].items()})
    if any(m.identity(Path(source)) != item for source, item in files.items()):
        raise RuntimeError("macro_training_feature_inputs_changed")
    models = load("stage006_monthly_models")
    if models.digest(SNAPSHOT) != "c5a166ee35972197d411de197d64408fb605889ab630f94549bda71d16f10435":
        raise RuntimeError("macro_training_label_snapshot_changed")
    data, oldspec, dataset_identity = models.load_verified_snapshot(SNAPSHOT)
    features = pd.read_csv(MACRO_OUTPUT / "event_macro_features.csv", float_precision="round_trip")
    spec = json.loads((MACRO_OUTPUT / "candidate_model_spec.json").read_text())
    combined = join_features(data, features, oldspec, spec)
    if len(combined) != 276 or len(spec["features"]) != 15:
        raise RuntimeError("macro_training_dimensions_changed")
    dataset_identity = {**dataset_identity, "macro_summary_sha256": models.digest(path),
                        "macro_features_sha256": models.digest(MACRO_OUTPUT / "event_macro_features.csv"),
                        "candidate_spec_sha256": models.digest(MACRO_OUTPUT / "candidate_model_spec.json")}
    labels = json.loads(SNAPSHOT.read_text())
    paths = {Path(source) for source in files} | {path, SNAPSHOT}
    paths.update(Path(source) for source in labels["source_identities"])
    paths.update(Path(item["path"]) for item in labels["output_identities"].values())
    return combined, spec, dataset_identity, paths


def run():
    if OUTPUT.exists():
        raise RuntimeError("macro_training_campaign_already_exists")
    data, spec, dataset_identity, paths = load_dataset()
    models = load("stage006_monthly_models")
    versions = load("stage006_training_campaign").check_versions(spec)
    batch = load("stage004_label_batch")
    _, runner = batch.configured()
    baseline_manifest = json.loads((batch.OUTPUT / "input_manifest.json").read_text())
    runner.validate_current_input_manifest(baseline_manifest)
    import pandas as pd
    import xgboost

    paths.update({Path(__file__).resolve(), CONTRACT, ROOT / "tests/test_stage015_macro_training.py",
                  ROOT / "tools/stage006_monthly_models.py", ROOT / "tools/stage006_training_campaign.py",
                  ROOT / "tools/stage008_model_catalog.py", ROOT / "stages/stage004_job_plan.json",
                  batch.OUTPUT / "input_manifest.json", Path(xgboost.sklearn.__file__), Path(xgboost.core._LIB._name)})
    sources = {str(path): runner._file_identity(path) for path in sorted(paths)}
    months = models.month_schedule(spec)
    lock = batch.OUTPUT / "run.lock"
    with lock.open("x") as stream:
        json.dump({"pid": os.getpid(), "mode": STAGE}, stream)
    month_index, predictions, started = {}, [], []
    try:
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / "input_manifest.json", {"source_identities": sources, "dataset_identity": dataset_identity,
                         "versions": versions, "months": months, "spec": spec,
                         "historical_evidence_type": spec["historical_evidence_type"]})
        network = runner.load_metadata_preflight_module().load_preflight_module().NetworkBlock()
        with network:
            for cutoff in months:
                started.append(cutoff)
                batch.write_json(OUTPUT / f"started_{cutoff}.json", {"cutoff": cutoff, "status": "fit_not_yet_called"})
                bundle = models.fit_month(data, cutoff, spec)
                model_root = OUTPUT / "models" / cutoff
                identity = models.save_bundle(bundle, model_root, spec)
                loaded = models.load_bundle(model_root, identity, spec)
                current = data.loc[data.decision_date.str[:7].eq(cutoff[:7])]
                for row in current.to_dict("records"):
                    features = {name: row[name] for name in spec["features"]}
                    before = models.predict_decision(bundle, row["decision_date"], row["product_vt_symbol"], features, spec)
                    after = models.predict_decision(loaded, row["decision_date"], row["product_vt_symbol"], features, spec)
                    if before != after:
                        raise RuntimeError("macro_saved_prediction_changed")
                    predictions.append({"event_id": row["event_id"], "candidate_index": row["candidate_index"],
                                        "decision_date": row["decision_date"], "product_vt_symbol": row["product_vt_symbol"], **after})
                month_index[cutoff] = {"metadata_sha256": identity, "status": bundle["status"],
                                       "train_count": bundle["train_count"], "fit_count": bundle["fit_count"],
                                       "train_frame_sha256": bundle["train_frame_sha256"]}
                print(json.dumps({"cutoff": cutoff, "status": bundle["status"], "train_count": bundle["train_count"]}), flush=True)
        if network.attempts:
            raise RuntimeError("macro_training_network_attempt")
        frame = pd.DataFrame(predictions).sort_values(["decision_date", "candidate_index"], kind="stable")
        if len(frame) != 276 or set(frame.event_id) != set(data.event_id):
            raise RuntimeError("macro_prediction_inventory_mismatch")
        runner.validate_current_input_manifest(baseline_manifest)
        if any(runner._file_identity(path) != item for path, item in sources.items()):
            raise RuntimeError("macro_training_input_changed")
        with (OUTPUT / "baseline_event_predictions.csv").open("x") as stream:
            frame.to_csv(stream, index=False, float_format="%.17g")
        batch.write_json(OUTPUT / "model_index.json", month_index)
        actions = frame.loc[frame.skip]
        summary = {"stage": STAGE, "status": "passed", "month_count": len(months),
                   "trained_month_count": sum(item["status"] == "trained" for item in month_index.values()),
                   "historical_model_fit_count": sum(item["fit_count"] for item in month_index.values()),
                   "baseline_prediction_count": len(frame), "baseline_predicted_skip_count": len(actions),
                   "first_baseline_skip_date": str(actions.decision_date.min()) if len(actions) else None,
                   "saved_prediction_mismatch_count": 0, "new_strategy_replay_count": 0,
                   "network_attempt_count": network.attempts, "reviewer_started": False,
                   "historical_vintage_verified": False, "historical_evidence_type": spec["historical_evidence_type"],
                   "output_identities": {name: runner._file_identity(OUTPUT / name)
                                         for name in ("input_manifest.json", "model_index.json", "baseline_event_predictions.csv")}}
        batch.write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary), flush=True)
        return summary
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / "failure.json").exists():
            batch.write_json(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "started_months": started,
                             "completed_months": list(month_index), "traceback": traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def load_catalog(root, expected_spec):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or (root / "failure.json").exists():
        raise RuntimeError("macro_training_not_complete")
    root = root.resolve()
    checker = load("stage008_model_catalog")
    summary_path = root / "summary.json"
    summary = json.loads(summary_path.read_text())
    if (summary["stage"] != STAGE or summary["status"] != "passed" or summary["baseline_prediction_count"] != 276
            or summary["saved_prediction_mismatch_count"] != 0 or summary["network_attempt_count"] != 0
            or summary["new_strategy_replay_count"] != 0 or summary["historical_evidence_type"] != expected_spec["historical_evidence_type"]):
        raise RuntimeError("macro_training_summary_invalid")
    if set(summary["output_identities"]) != {"input_manifest.json", "model_index.json", "baseline_event_predictions.csv"}:
        raise RuntimeError("macro_catalog_outputs_invalid")
    files = [summary_path]
    for name, item in summary["output_identities"].items():
        checker.verify_file(root / name, item)
        files.append(root / name)
    manifest = json.loads((root / "input_manifest.json").read_text())
    if (manifest["spec"] != expected_spec or manifest["versions"] != expected_spec["versions"]
            or manifest["historical_evidence_type"] != expected_spec["historical_evidence_type"]):
        raise RuntimeError("macro_catalog_spec_changed")
    for source, item in manifest["source_identities"].items():
        checker.verify_file(source, item)
        files.append(Path(source))
    models = load("stage006_monthly_models")
    months = models.month_schedule(expected_spec)
    index = json.loads((root / "model_index.json").read_text())
    if (manifest["months"] != months or set(index) != set(months) or summary["month_count"] != len(months)
            or summary["trained_month_count"] != sum(row["status"] == "trained" for row in index.values())
            or summary["historical_model_fit_count"] != sum(row["fit_count"] for row in index.values())):
        raise RuntimeError("macro_catalog_month_inventory_invalid")
    registry, count = {}, 0
    for cutoff in months:
        model_files = checker.read_metadata(root, cutoff, index[cutoff], expected_spec, models.spec_digest(expected_spec))
        count += len(model_files) - 1
        files.extend(model_files)
        registry[cutoff] = {"root": root / "models" / cutoff, "metadata_sha256": index[cutoff]["metadata_sha256"]}
    return registry, expected_spec, {"summary_sha256": models.digest(summary_path), "metadata_count": len(registry),
                                    "model_file_count": count, "files": sorted(set(files)),
                                    "dataset_identity": manifest["dataset_identity"]}


if __name__ == "__main__":
    run()
