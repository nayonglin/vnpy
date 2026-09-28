from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage031_migration_training"
OUTPUT = ROOT / "artifacts" / STAGE
FEATURE_OUTPUT = ROOT / "artifacts/stage030_migration_features"
FEATURE_SHA = "f438d3e22a8d646d0de7610073bfd7d0eceee43edb6a09106ee7782a5298c83a"
SNAPSHOT = ROOT / "artifacts/stage005_label_collection/20260906_020434_393264/summary.json"
CONTRACT = ROOT / "stages/20260906_0730_stage031_032_migration_candidate_contract.md"
ID_COLUMNS = ["event_id", "candidate_index", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]


def load(name):
    spec = importlib.util.spec_from_file_location("migration_training_" + name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def migration():
    return load("stage030_migration_features")


def join_features(data, features, oldspec, spec):
    import numpy as np
    import pandas as pd

    m = migration()
    if spec != m.candidate_spec(oldspec):
        raise RuntimeError("migration_training_spec_changed")
    if (set(features.columns) != set(ID_COLUMNS + ["source_date", "window_start"] + m.FEATURES)
            or set(m.FEATURES) & set(data.columns)
            or data.event_id.isna().any() or data.event_id.duplicated().any()
            or features.event_id.isna().any() or features.event_id.duplicated().any()
            or len(data) != len(features) or set(data.event_id) != set(features.event_id)):
        raise RuntimeError("migration_training_event_inventory_invalid")
    ordered = features.set_index("event_id").loc[data.event_id].reset_index()
    if not ordered[ID_COLUMNS].equals(data[ID_COLUMNS].reset_index(drop=True)):
        raise RuntimeError("migration_training_event_identity_mismatch")
    for name in ("decision_date", "source_date", "window_start"):
        m.coverage.dates(ordered[name])
    if not (ordered.window_start.lt(ordered.source_date) & ordered.source_date.lt(ordered.decision_date)).all():
        raise RuntimeError("migration_training_source_not_past")
    if not np.isfinite(ordered[m.FEATURES].to_numpy(dtype=float)).all():
        raise RuntimeError("migration_training_features_nonfinite")
    result = data.copy(deep=True)
    for name in m.FEATURES:
        result[name] = ordered[name].to_numpy(copy=True)
    pd.testing.assert_frame_equal(result[data.columns], data, check_exact=True)
    return result


def load_dataset():
    import pandas as pd

    m = migration()
    path = FEATURE_OUTPUT / "summary.json"
    if m.base.identity(path)["sha256"] != FEATURE_SHA:
        raise RuntimeError("migration_training_source_summary_changed")
    summary = json.loads(path.read_text())
    if summary["status"] != "migration_features_qualified_no_models" or summary["event_count"] != 276:
        raise RuntimeError("migration_training_features_not_qualified")
    files = json.loads((FEATURE_OUTPUT / "input_manifest.json").read_text())
    files.update({str(FEATURE_OUTPUT / name): item for name, item in summary["outputs"].items()})
    if any(m.base.identity(source) != item for source, item in files.items()):
        raise RuntimeError("migration_training_feature_inputs_changed")
    models = load("stage006_monthly_models")
    if models.digest(SNAPSHOT) != "c5a166ee35972197d411de197d64408fb605889ab630f94549bda71d16f10435":
        raise RuntimeError("migration_training_label_snapshot_changed")
    data, oldspec, dataset_identity = models.load_verified_snapshot(SNAPSHOT)
    features = pd.read_csv(FEATURE_OUTPUT / "event_migration_features.csv", float_precision="round_trip")
    spec = json.loads((FEATURE_OUTPUT / "candidate_model_spec.json").read_text())
    combined = join_features(data, features, oldspec, spec)
    if len(combined) != 276 or len(spec["features"]) != 12:
        raise RuntimeError("migration_training_dimensions_changed")
    dataset_identity = {**dataset_identity, "migration_summary_sha256": models.digest(path),
        "migration_features_sha256": models.digest(FEATURE_OUTPUT / "event_migration_features.csv"),
        "candidate_spec_sha256": models.digest(FEATURE_OUTPUT / "candidate_model_spec.json")}
    labels = json.loads(SNAPSHOT.read_text())
    paths = {Path(source) for source in files} | {path, SNAPSHOT, Path(__file__).resolve(), CONTRACT,
        ROOT / "tests/test_stage031_migration_training.py", ROOT / "tools/stage015_macro_training.py"}
    paths.update(Path(source) for source in labels["source_identities"])
    paths.update(Path(item["path"]) for item in labels["output_identities"].values())
    return combined, spec, dataset_identity, paths


def campaign():
    # Reuse the verified campaign machinery without changing its frozen source.
    parent = load("stage015_macro_training")
    parent.STAGE, parent.OUTPUT, parent.CONTRACT = STAGE, OUTPUT, CONTRACT
    parent.load_dataset = load_dataset
    parent.__file__ = str(Path(__file__).resolve())
    return parent


def run():
    return campaign().run()


def load_catalog(root, expected_spec):
    return campaign().load_catalog(root, expected_spec)


if __name__ == "__main__":
    run()
