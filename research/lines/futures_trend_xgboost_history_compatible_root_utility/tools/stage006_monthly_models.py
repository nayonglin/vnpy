from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def spec_digest(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def require_complete_summary(summary):
    if (summary.get("status") != "passed" or summary.get("training_ready") is not True
            or summary.get("completed") != 274 or summary.get("planned") != 274
            or summary.get("pending") != 0 or summary.get("censored") != 2
            or summary.get("unfinished_job_ids") != []):
        raise RuntimeError("training_inventory_incomplete")


def load_verified_snapshot(path):
    import pandas as pd

    path = Path(path).resolve(strict=True)
    path.relative_to(ROOT / "artifacts/stage005_label_collection")
    summary = json.loads(path.read_text())
    require_complete_summary(summary)
    module_spec = importlib.util.spec_from_file_location("monthly_collection", ROOT / "tools/stage005_label_collection.py")
    collector = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(collector)
    for source, identity in summary["source_identities"].items():
        collector.verify_identity(source, identity)
    for identity in summary["output_identities"].values():
        collector.verify_identity(identity["path"], identity)
    model_path = ROOT / "stages/stage004_model_spec.json"
    plan = json.loads((ROOT / "stages/stage004_job_plan.json").read_text())
    if digest(model_path) != plan["model_spec_sha256"]:
        raise RuntimeError("frozen_model_spec_changed")
    spec = json.loads(model_path.read_text())
    dataset_path = path.parent / "events.csv"
    if str(dataset_path) != summary["output_identities"]["events.csv"]["path"]:
        raise RuntimeError("snapshot_dataset_path_mismatch")
    data = pd.read_csv(dataset_path, float_precision="round_trip")
    expected = {event["event_id"] for event in [*plan["jobs"], *plan["censored"]]}
    if len(data) != 276 or set(data.event_id) != expected or int(data.label_status.eq("verified").sum()) != 274:
        raise RuntimeError("snapshot_event_inventory_mismatch")
    return data, spec, {"snapshot_sha256": digest(path), "dataset_sha256": digest(dataset_path),
                        "model_spec_sha256": digest(model_path)}


def month_schedule(spec):
    import pandas as pd
    return [stamp.strftime("%Y-%m-01") for stamp in pd.period_range(spec["analysis_start"], spec["analysis_end"], freq="M")]


def validate_cutoff(cutoff):
    try:
        value = date.fromisoformat(cutoff)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("cutoff_not_month_start") from exc
    if value.day != 1 or value.isoformat() != cutoff:
        raise RuntimeError("cutoff_not_month_start")


def feature_matrix(data, spec):
    import numpy as np
    if not set(spec["features"]).issubset(data.columns):
        raise RuntimeError("model_feature_missing")
    result = data.loc[:, spec["features"]].astype(float)
    if not np.isfinite(result.to_numpy()).all():
        raise RuntimeError("model_feature_nonfinite")
    return result


def training_rows(data, cutoff, spec):
    import numpy as np
    import pandas as pd

    validate_cutoff(cutoff)
    required = {"event_id", "decision_date", "label_end_date", "label_status", "lifecycle_status",
                "product_vt_symbol", *spec["features"], *spec["targets"]}
    if (not required.issubset(data.columns) or data.event_id.isna().any() or data.event_id.duplicated().any()
            or data.product_vt_symbol.eq("fu.SHFE").any() or not data.label_status.isin(["verified", "censored"]).all()):
        raise RuntimeError("training_dataset_invalid")
    feature_matrix(data, spec)
    closed = data.label_status.eq("verified")
    if (not data.loc[closed, "lifecycle_status"].isin(["mature", "mature_cancelled_unfilled"]).all()
            or not data.loc[~closed, "lifecycle_status"].isin(["right_censored_open", "right_censored_pending_entry"]).all()
            or data.loc[~closed, "label_end_date"].notna().any()
            or data.loc[~closed, spec["targets"]].notna().any().any()
            or not np.isfinite(data.loc[closed, spec["targets"]].to_numpy(dtype=float)).all()):
        raise RuntimeError("training_lifecycle_or_target_invalid")
    for values in (data.decision_date, data.loc[closed, "label_end_date"]):
        if (not values.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
                or pd.to_datetime(values, errors="coerce").isna().any()):
            raise RuntimeError("training_date_invalid")
    if data.loc[closed, "label_end_date"].lt(data.loc[closed, "decision_date"]).any():
        raise RuntimeError("label_ends_before_decision")
    return data.loc[closed & data.decision_date.lt(cutoff) & data.label_end_date.fillna("9999-12-31").lt(cutoff)].copy()


def fit_month(data, cutoff, spec, estimator_factory=None):
    import numpy as np

    train = training_rows(data, cutoff, spec)
    columns = ["event_id", "decision_date", "label_end_date", *spec["features"], *spec["targets"]]
    signature = hashlib.sha256(train.loc[:, columns].to_csv(index=False, float_format="%.17g").encode()).hexdigest()
    bundle = {"cutoff": cutoff, "status": "untrained", "train_event_ids": train.event_id.tolist(),
              "train_frame_sha256": signature, "train_count": len(train), "spec_sha256": spec_digest(spec),
              "max_train_decision": str(train.decision_date.max()) if len(train) else None,
              "max_train_end": str(train.label_end_date.max()) if len(train) else None, "heads": {}, "fit_count": 0}
    if len(train) < spec["training"]["minimum_mature_events"]:
        return bundle
    features = feature_matrix(train, spec)
    for target in spec["targets"]:
        values = train[target].to_numpy(dtype=float)
        constant = bool(np.all(values == values[0]))
        mean = float(values[0] if constant else values.mean())
        std = 0.0 if constant else float(values.std(ddof=0))
        if not math.isfinite(mean) or not math.isfinite(std) or (not constant and std <= 0):
            raise RuntimeError("target_transform_invalid")
        head = {"kind": "constant" if constant else "xgboost", "mean": mean, "std": std, "estimator": None}
        if not constant:
            if estimator_factory is None:
                from xgboost import XGBRegressor
                estimator_factory = XGBRegressor
            head["estimator"] = estimator_factory(**spec["estimator"])
            head["estimator"].fit(features, (values - mean) / std)
            bundle["fit_count"] += 1
        bundle["heads"][target] = head
    bundle["status"] = "trained"
    return bundle


def predict_bundle(bundle, data, spec):
    import numpy as np

    if bundle["spec_sha256"] != spec_digest(spec):
        raise RuntimeError("model_spec_mismatch")
    if bundle["status"] == "untrained":
        return None
    if bundle["status"] != "trained" or set(bundle["heads"]) != set(spec["targets"]):
        raise RuntimeError("model_heads_invalid")
    features = feature_matrix(data, spec)
    result = {}
    for target, head in bundle["heads"].items():
        values = (np.full(len(data), head["mean"], dtype=float) if head["kind"] == "constant"
                  else np.asarray(head["estimator"].predict(features), dtype=float) * head["std"] + head["mean"])
        if values.shape != (len(data),) or not np.isfinite(values).all():
            raise RuntimeError("nonfinite_prediction")
        result[target] = values
    return result


def should_skip(return_prediction, drawdown_prediction, product):
    if product == "fu.SHFE" or (return_prediction is None and drawdown_prediction is None):
        return False
    if return_prediction is None or drawdown_prediction is None:
        raise RuntimeError("incomplete_prediction")
    if not math.isfinite(return_prediction) or not math.isfinite(drawdown_prediction):
        raise RuntimeError("nonfinite_prediction")
    return bool(return_prediction < 0 and drawdown_prediction < 0)


def predict_decision(bundle, decision_date, product, current_features, spec):
    import pandas as pd

    try:
        parsed = date.fromisoformat(decision_date)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("decision_date_invalid") from exc
    if parsed.isoformat() != decision_date:
        raise RuntimeError("decision_date_invalid")
    cutoff = parsed.replace(day=1).isoformat()
    result = {"cutoff": cutoff, "status": "untrained", "skip": False,
              "return_marginal": None, "drawdown_marginal": None}
    if product == "fu.SHFE":
        return {**result, "status": "fixed_fu"}
    if bundle is None:
        return result
    if bundle["cutoff"] != cutoff:
        raise RuntimeError("decision_model_month_mismatch")
    if bundle["spec_sha256"] != spec_digest(spec):
        raise RuntimeError("model_spec_mismatch")
    if bundle["status"] == "untrained":
        return result
    predictions = predict_bundle(bundle, pd.DataFrame([current_features]), spec)
    for target in spec["targets"]:
        result[target] = float(predictions[target][0])
    result["status"] = "predicted"
    result["skip"] = should_skip(result["return_marginal"], result["drawdown_marginal"], product)
    return result


def save_bundle(bundle, root, spec):
    root = Path(root)
    if bundle["spec_sha256"] != spec_digest(spec):
        raise RuntimeError("model_spec_mismatch")
    root.mkdir(parents=True, exist_ok=False)
    metadata = {key: value for key, value in bundle.items() if key != "heads"}
    metadata["heads"] = {}
    for target, head in bundle["heads"].items():
        item = {key: value for key, value in head.items() if key != "estimator"}
        if head["kind"] == "xgboost":
            path = root / f"{target}.ubj"
            head["estimator"].save_model(path)
            item["model_sha256"] = digest(path)
        metadata["heads"][target] = item
    path = root / "metadata.json"
    with path.open("x") as stream:
        json.dump(metadata, stream, sort_keys=True, indent=2, allow_nan=False)
    return digest(path)


def load_bundle(root, expected_metadata_sha256, spec):
    root = Path(root)
    path = root / "metadata.json"
    if digest(path) != expected_metadata_sha256:
        raise RuntimeError("model_metadata_changed")
    bundle = json.loads(path.read_text())
    validate_cutoff(bundle["cutoff"])
    if (bundle["spec_sha256"] != spec_digest(spec) or bundle["train_count"] != len(bundle["train_event_ids"])
            or len(set(bundle["train_event_ids"])) != bundle["train_count"]
            or (bundle["max_train_end"] and bundle["max_train_end"] >= bundle["cutoff"])
            or (bundle["max_train_decision"] and bundle["max_train_decision"] >= bundle["cutoff"])):
        raise RuntimeError("model_training_identity_invalid")
    trained = bundle["train_count"] >= spec["training"]["minimum_mature_events"]
    if (bundle["status"] != ("trained" if trained else "untrained")
            or set(bundle["heads"]) != (set(spec["targets"]) if trained else set())):
        raise RuntimeError("model_heads_invalid")
    for target, head in bundle["heads"].items():
        if not math.isfinite(head["mean"]) or not math.isfinite(head["std"]):
            raise RuntimeError("target_transform_invalid")
        head["estimator"] = None
        if head["kind"] == "xgboost" and head["std"] > 0:
            path = root / f"{target}.ubj"
            if digest(path) != head["model_sha256"]:
                raise RuntimeError("model_file_changed")
            from xgboost import XGBRegressor
            head["estimator"] = XGBRegressor(n_jobs=spec["estimator"]["n_jobs"])
            head["estimator"].load_model(path)
        elif head["kind"] != "constant" or head["std"] != 0:
            raise RuntimeError("model_head_invalid")
    return bundle
