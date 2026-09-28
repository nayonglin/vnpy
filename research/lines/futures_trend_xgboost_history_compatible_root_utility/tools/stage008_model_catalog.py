from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_file(path, identity):
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or str(path.resolve()) != identity["path"]
            or path.stat().st_size != identity["size"] or digest(path) != identity["sha256"]):
        raise RuntimeError(f"catalog_file_changed:{path}")


def read_metadata(root, cutoff, entry, spec, spec_sha):
    path = root / "models" / cutoff / "metadata.json"
    if path.is_symlink() or path.parent.is_symlink() or digest(path) != entry["metadata_sha256"]:
        raise RuntimeError("catalog_metadata_changed")
    meta = json.loads(path.read_text())
    if (meta["cutoff"] != cutoff or meta["spec_sha256"] != spec_sha
            or any(meta[key] != entry[key] for key in ("status", "train_count", "fit_count", "train_frame_sha256"))
            or len(meta["train_event_ids"]) != meta["train_count"]
            or len(set(meta["train_event_ids"])) != meta["train_count"]):
        raise RuntimeError("catalog_training_identity_invalid")
    for name in ("max_train_decision", "max_train_end"):
        value = meta[name]
        if value is None:
            if meta["train_count"]:
                raise RuntimeError("catalog_training_date_missing")
        elif date.fromisoformat(value).isoformat() != value or value >= cutoff:
            raise RuntimeError("catalog_training_date_not_past")
    trained = meta["train_count"] >= spec["training"]["minimum_mature_events"]
    if (meta["status"] != ("trained" if trained else "untrained")
            or set(meta["heads"]) != (set(spec["targets"]) if trained else set())):
        raise RuntimeError("catalog_head_inventory_invalid")
    files = [path]
    for name, head in meta["heads"].items():
        if (not math.isfinite(head["mean"]) or not math.isfinite(head["std"])
                or head["kind"] not in {"constant", "xgboost"}
                or (head["kind"] == "constant" and head["std"] != 0)
                or (head["kind"] == "xgboost" and head["std"] <= 0)):
            raise RuntimeError("catalog_target_transform_invalid")
        if head["kind"] == "xgboost":
            model = path.parent / f"{name}.ubj"
            if model.is_symlink() or digest(model) != head["model_sha256"]:
                raise RuntimeError("catalog_native_model_changed")
            files.append(model)
    if len(files) - 1 != meta["fit_count"]:
        raise RuntimeError("catalog_fit_count_invalid")
    return files


def load_catalog(root, expected_spec):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or (root / "failure.json").exists():
        raise RuntimeError("training_campaign_not_complete")
    root = root.resolve()
    summary_path = root / "summary.json"
    summary = json.loads(summary_path.read_text())
    if (summary["stage"] != "stage006_monthly_fit" or summary["status"] != "passed"
            or summary["baseline_prediction_count"] != 276 or summary["saved_prediction_mismatch_count"] != 0
            or summary["network_attempt_count"] != 0 or summary["new_strategy_replay_count"] != 0
            or summary["historical_evidence_type"] != expected_spec["historical_evidence_type"]):
        raise RuntimeError("training_campaign_summary_invalid")
    expected_outputs = {"input_manifest.json", "model_index.json", "baseline_event_predictions.csv"}
    if set(summary["output_identities"]) != expected_outputs:
        raise RuntimeError("catalog_output_inventory_invalid")
    files = [summary_path]
    for name, identity in summary["output_identities"].items():
        verify_file(root / name, identity)
        files.append(root / name)
    manifest = json.loads((root / "input_manifest.json").read_text())
    if (manifest["spec"] != expected_spec or manifest["versions"] != expected_spec["versions"]
            or manifest["historical_evidence_type"] != expected_spec["historical_evidence_type"]):
        raise RuntimeError("catalog_spec_changed")
    for source, identity in manifest["source_identities"].items():
        verify_file(source, identity)
        files.append(Path(source))
    module_spec = importlib.util.spec_from_file_location("catalog_monthly", ROOT / "tools/stage006_monthly_models.py")
    monthly = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(monthly)
    months = monthly.month_schedule(expected_spec)
    index = json.loads((root / "model_index.json").read_text())
    if (manifest["months"] != months or set(index) != set(months) or summary["month_count"] != len(months)
            or summary["trained_month_count"] != sum(row["status"] == "trained" for row in index.values())
            or summary["historical_model_fit_count"] != sum(row["fit_count"] for row in index.values())):
        raise RuntimeError("catalog_month_inventory_invalid")
    registry, native_count = {}, 0
    spec_sha = monthly.spec_digest(expected_spec)
    for cutoff in months:
        model_files = read_metadata(root, cutoff, index[cutoff], expected_spec, spec_sha)
        native_count += len(model_files) - 1
        files.extend(model_files)
        registry[cutoff] = {"root": root / "models" / cutoff, "metadata_sha256": index[cutoff]["metadata_sha256"]}
    return registry, expected_spec, {"summary_sha256": digest(summary_path), "metadata_count": len(registry),
                                    "model_file_count": native_count, "files": sorted(set(files)),
                                    "dataset_identity": manifest["dataset_identity"]}
