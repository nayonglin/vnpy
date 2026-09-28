from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage006_monthly_fit"
CONTRACT = ROOT / "stages/20260905_2114_stage006_training_contract.md"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_versions(spec):
    actual = {name: importlib.metadata.version(name) for name in spec["versions"]}
    if actual != spec["versions"]:
        raise RuntimeError("training_dependency_version_changed")
    return actual


def run_campaign(snapshot):
    models = load("campaign_monthly_models", ROOT / "tools/stage006_monthly_models.py")
    data, spec, dataset_identity = models.load_verified_snapshot(snapshot)
    versions = check_versions(spec)
    if OUTPUT.exists():
        raise RuntimeError("training_campaign_already_exists")
    batch = load("training_batch_support", ROOT / "tools/stage004_label_batch.py")
    _, runner = batch.configured()
    manifest = json.loads((batch.OUTPUT / "input_manifest.json").read_text())
    runner.validate_current_input_manifest(manifest)
    lock = batch.OUTPUT / "run.lock"
    with lock.open("x") as stream:
        json.dump({"pid": os.getpid(), "mode": "stage006_monthly_fit"}, stream)
    month_index = {}
    try:
        import pandas as pd
        import xgboost

        sources = [Path(__file__).resolve(), Path(models.__file__), CONTRACT, Path(snapshot).resolve(),
                   ROOT / "tests/test_stage006_monthly_models.py", ROOT / "tests/test_stage006_training_campaign.py",
                   ROOT / "stages/stage004_model_spec.json", ROOT / "stages/stage004_job_plan.json",
                   batch.OUTPUT / "input_manifest.json", Path(xgboost.sklearn.__file__), Path(xgboost.core._LIB._name)]
        source_identities = {str(path): runner._file_identity(path) for path in sources}
        months = models.month_schedule(spec)
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / "input_manifest.json", {"source_identities": source_identities,
                         "dataset_identity": dataset_identity, "versions": versions, "months": months,
                         "spec": spec, "historical_evidence_type": spec["historical_evidence_type"]})
        network = runner.load_metadata_preflight_module().load_preflight_module().NetworkBlock()
        predictions = []
        with network:
            for cutoff in months:
                bundle = models.fit_month(data, cutoff, spec)
                root = OUTPUT / "models" / cutoff
                identity = models.save_bundle(bundle, root, spec)
                loaded = models.load_bundle(root, identity, spec)
                current = data.loc[data.decision_date.str[:7].eq(cutoff[:7])]
                for row in current.to_dict("records"):
                    features = {name: row[name] for name in spec["features"]}
                    before = models.predict_decision(bundle, row["decision_date"], row["product_vt_symbol"], features, spec)
                    after = models.predict_decision(loaded, row["decision_date"], row["product_vt_symbol"], features, spec)
                    if before != after:
                        raise RuntimeError("saved_model_prediction_changed")
                    predictions.append({"event_id": row["event_id"], "candidate_index": row["candidate_index"],
                                        "decision_date": row["decision_date"], "product_vt_symbol": row["product_vt_symbol"], **after})
                month_index[cutoff] = {"metadata_sha256": identity, "status": bundle["status"],
                                       "train_count": bundle["train_count"], "fit_count": bundle["fit_count"],
                                       "train_frame_sha256": bundle["train_frame_sha256"]}
                print(json.dumps({"cutoff": cutoff, **month_index[cutoff]}), flush=True)
        if network.attempts:
            raise RuntimeError("training_network_attempt")
        prediction_frame = pd.DataFrame(predictions).sort_values(["decision_date", "candidate_index"], kind="stable")
        if len(prediction_frame) != 276 or set(prediction_frame.event_id) != set(data.event_id):
            raise RuntimeError("prediction_inventory_mismatch")
        runner.validate_current_input_manifest(manifest)
        for path, identity in source_identities.items():
            if runner._file_identity(path) != identity:
                raise RuntimeError(f"training_input_changed:{path}")
        with (OUTPUT / "baseline_event_predictions.csv").open("x") as stream:
            prediction_frame.to_csv(stream, index=False, float_format="%.17g")
        batch.write_json(OUTPUT / "model_index.json", month_index)
        actions = prediction_frame.loc[prediction_frame.skip]
        summary = {"stage": "stage006_monthly_fit", "status": "passed", "month_count": len(months),
                   "trained_month_count": sum(item["status"] == "trained" for item in month_index.values()),
                   "historical_model_fit_count": sum(item["fit_count"] for item in month_index.values()),
                   "baseline_prediction_count": len(prediction_frame), "baseline_predicted_skip_count": len(actions),
                   "first_baseline_skip_date": str(actions.decision_date.min()) if len(actions) else None,
                   "saved_prediction_mismatch_count": 0, "new_strategy_replay_count": 0,
                   "network_attempt_count": network.attempts, "reviewer_started": False,
                   "historical_evidence_type": spec["historical_evidence_type"],
                   "output_identities": {name: runner._file_identity(OUTPUT / name)
                                         for name in ("input_manifest.json", "model_index.json", "baseline_event_predictions.csv")}}
        batch.write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / "failure.json").exists():
            batch.write_json(OUTPUT / "failure.json", {"status": "failed", "error": str(exc),
                             "completed_month_count": len(month_index), "historical_fit_attempts_may_have_occurred": True,
                             "traceback": traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    run_campaign(args.snapshot)


if __name__ == "__main__":
    main()
