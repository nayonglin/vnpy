from __future__ import annotations

import importlib.util
import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage010_failure_diagnostics"
SNAPSHOT = ROOT / "artifacts/stage005_label_collection/20260906_020434_393264/summary.json"
CONTRACT = ROOT / "stages/20260906_0222_stage010_diagnostic_contract.md"
TARGETS = ("return_marginal", "drawdown_marginal")
MATCH_KEYS = ("decision_datetime", "product_vt_symbol", "contract_vt_symbol", "direction", "signal", "entry_context")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def ratio(numerator, denominator):
    return float(numerator / denominator) if denominator else None


def regression_metrics(actual, predicted, baseline, scale):
    y, p, b, s = (np.asarray(value, dtype=float) for value in (actual, predicted, baseline, scale))
    if (y.ndim != 1 or any(value.shape != y.shape for value in (p, b, s))
            or not all(np.isfinite(value).all() for value in (y, p, b, s)) or (s < 0).any()):
        raise RuntimeError("scoring_inputs_invalid")
    ep, eb = p - y, b - y
    model_mse = float(np.mean(ep ** 2)) if len(y) else None
    baseline_mse = float(np.mean(eb ** 2)) if len(y) else None
    valid = s > 0
    normalized_p = float(np.mean((ep[valid] / s[valid]) ** 2)) if valid.any() else None
    normalized_b = float(np.mean((eb[valid] / s[valid]) ** 2)) if valid.any() else None
    return {"count": len(y), "model_mse": model_mse, "baseline_mse": baseline_mse,
            "mse_skill": 1 - model_mse / baseline_mse if baseline_mse else None,
            "model_mae": float(np.mean(abs(ep))) if len(y) else None,
            "baseline_mae": float(np.mean(abs(eb))) if len(y) else None,
            "mean_prediction_error": float(np.mean(ep)) if len(y) else None,
            "standardized_count": int(valid.sum()), "standardized_model_mse": normalized_p,
            "standardized_baseline_mse": normalized_b,
            "standardized_mse_skill": 1 - normalized_p / normalized_b if normalized_b else None,
            "pearson": float(np.corrcoef(y, p)[0, 1]) if len(y) > 1 and y.std() > 0 and p.std() > 0 else None}


def join_predictions(events, predictions, metadata):
    ids = ["event_id", "candidate_index", "decision_date", "product_vt_symbol"]
    for frame in (events, predictions):
        if frame.event_id.isna().any() or frame.event_id.duplicated().any():
            raise RuntimeError("diagnostic_event_inventory_invalid")
    if set(events.event_id) != set(predictions.event_id):
        raise RuntimeError("diagnostic_prediction_inventory_mismatch")
    left = events.sort_values("event_id").reset_index(drop=True)
    right = predictions.sort_values("event_id").reset_index(drop=True)
    if not left[ids].equals(right[ids]):
        raise RuntimeError("diagnostic_prediction_identity_mismatch")
    if (not left.label_status.isin(["verified", "censored"]).all()
            or left.loc[left.label_status.eq("censored"), list(TARGETS)].notna().any().any()
            or not np.isfinite(left.loc[left.label_status.eq("verified"), list(TARGETS)].to_numpy()).all()):
        raise RuntimeError("diagnostic_label_status_invalid")
    columns = ["event_id", "cutoff", "status", "skip", *TARGETS]
    joined = events.merge(predictions[columns].rename(columns={key: f"pred_{key}" for key in TARGETS}),
                          on="event_id", how="left", validate="one_to_one", sort=False)
    for target in TARGETS:
        joined[f"baseline_{target}"] = np.nan
        joined[f"scale_{target}"] = np.nan
    for index, row in joined.iterrows():
        cutoff = row.decision_date[:7] + "-01"
        if row.cutoff != cutoff or cutoff not in metadata:
            raise RuntimeError("diagnostic_prediction_month_mismatch")
        meta = metadata[cutoff]
        if meta["status"] == "untrained":
            if row.status != "untrained" or row.skip or any(pd.notna(row[f"pred_{key}"]) for key in TARGETS):
                raise RuntimeError("diagnostic_untrained_prediction_invalid")
        elif meta["status"] == "trained":
            scores = [row[f"pred_{key}"] for key in TARGETS]
            if (row.status != "predicted" or not np.isfinite(scores).all()
                    or not isinstance(row.skip, (bool, np.bool_)) or row.skip != all(value < 0 for value in scores)):
                raise RuntimeError("diagnostic_prediction_action_invalid")
            for target in TARGETS:
                joined.loc[index, f"baseline_{target}"] = meta["heads"][target]["mean"]
                joined.loc[index, f"scale_{target}"] = meta["heads"][target]["std"]
        else:
            raise RuntimeError("diagnostic_model_status_invalid")
    joined["evaluable"] = joined.label_status.eq("verified") & joined.status.eq("predicted")
    return joined


def action_metrics(joined):
    data = joined.loc[joined.evaluable]
    truth = data.loc[:, list(TARGETS)].lt(0).all(axis=1)
    skipped = data.skip
    tp, fp = int((truth & skipped).sum()), int((~truth & skipped).sum())
    fn, tn = int((truth & ~skipped).sum()), int((~truth & ~skipped).sum())
    return {"evaluated_count": len(data), "skip_count": int(skipped.sum()),
            "true_harm_count": int(truth.sum()), "true_harm_rate": ratio(int(truth.sum()), len(data)),
            "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
            "skip_precision": ratio(tp, tp + fp), "harm_recall": ratio(tp, tp + fn),
            "skipped_positive_return_count": int((skipped & data.return_marginal.gt(0)).sum()),
            "skipped_positive_both_count": int((skipped & data[list(TARGETS)].gt(0).all(axis=1)).sum()),
            "skipped_negative_return_count": int((skipped & data.return_marginal.lt(0)).sum()),
            "skipped_zero_return_count": int((skipped & data.return_marginal.eq(0)).sum())}


def path_drift(a, c, features):
    columns = [*MATCH_KEYS, "event_id", "candidate_index", "skip", *features]
    for frame in (a, c):
        if frame.loc[:, list(MATCH_KEYS)].isna().any().any() or frame.duplicated(list(MATCH_KEYS)).any():
            raise RuntimeError("path_key_missing_or_duplicate")
        if not np.isfinite(frame.loc[:, features].to_numpy(dtype=float)).all():
            raise RuntimeError("path_feature_nonfinite")
    merged = a[columns].merge(c[columns], on=list(MATCH_KEYS), how="outer", suffixes=("_a", "_c"),
                              validate="one_to_one", indicator=True, sort=True)
    paired = merged.loc[merged._merge.eq("both")].copy()
    changed = {}
    for name in features:
        paired[f"delta_{name}"] = paired[f"{name}_c"] - paired[f"{name}_a"]
        changed[name] = int(paired[f"delta_{name}"].ne(0).sum())
    paired["action_changed"] = paired.skip_a.ne(paired.skip_c)
    return paired, {"a_count": len(a), "c_count": len(c), "common_count": len(paired),
                    "a_only_count": int(merged._merge.eq("left_only").sum()),
                    "c_only_count": int(merged._merge.eq("right_only").sum()),
                    "action_changed_count": int(paired.action_changed.sum()),
                    "a_skip_common_count": int(paired.skip_a.sum()), "c_skip_common_count": int(paired.skip_c.sum()),
                    "feature_changed_counts": changed}


def validate_training_statistics(events, metadata, spec, monthly):
    for cutoff, meta in metadata.items():
        train = monthly.training_rows(events, cutoff, spec)
        if train.event_id.tolist() != meta["train_event_ids"]:
            raise RuntimeError("diagnostic_training_ids_changed")
        for target, head in meta["heads"].items():
            values = train[target].to_numpy(dtype=float)
            constant = bool(np.all(values == values[0]))
            mean = float(values[0] if constant else values.mean())
            std = 0.0 if constant else float(values.std(ddof=0))
            if mean != head["mean"] or std != head["std"]:
                raise RuntimeError("diagnostic_training_transform_changed")


def run():
    if OUTPUT.exists():
        raise RuntimeError("diagnostic_output_already_exists")
    replay = load("diagnostic_replay_support", "stage009_full_path_replay.py")
    batch, _, runner = replay.configured()
    manifest = json.loads((replay.OUTPUT / "input_manifest.json").read_text())
    runner.validate_current_input_manifest(manifest)
    batch.verify_baseline_inputs(manifest)
    monthly = load("diagnostic_monthly_support", "stage006_monthly_models.py")
    events, spec, dataset_identity = monthly.load_verified_snapshot(SNAPSHOT)
    registry, _, catalog = replay.catalog()
    if dataset_identity != catalog["dataset_identity"]:
        raise RuntimeError("diagnostic_dataset_identity_mismatch")
    summary_path = replay.OUTPUT / "summary.json"
    summary = json.loads(summary_path.read_text())
    root = replay.OUTPUT / "workers/C"
    receipt = json.loads((root / "receipt.json").read_text())
    if summary["status"] != "passed" or batch.digest(root / "receipt.json") != summary["receipt_sha256"]:
        raise RuntimeError("diagnostic_c_receipt_changed")
    replay.validate_worker_receipt(receipt, manifest, receipt["audit"]["source_sha256"])
    collector = load("diagnostic_collector_support", "stage005_label_collection.py")
    archives = json.loads((root / "archive_receipt.json").read_text())
    if set(archives) != set(replay.FRAME_NAMES):
        raise RuntimeError("diagnostic_c_archive_inventory_invalid")
    for name, identity in archives.items():
        if identity["raw_sha256"] != receipt["frames"][name]["sha256"]:
            raise RuntimeError("diagnostic_c_archive_receipt_mismatch")
        collector.verify_archive(root / f"{name}.csv.gz", identity)
    snapshot_summary = json.loads(SNAPSHOT.read_text())
    files = {Path(identity["path"]) for identity in manifest["files"].values()}
    files.update(Path(path) for path in snapshot_summary["source_identities"])
    files.update(Path(identity["path"]) for identity in snapshot_summary["output_identities"].values())
    files.update(catalog["files"])
    files.update([Path(__file__), CONTRACT, ROOT / "tests/test_stage010_failure_diagnostics.py", SNAPSHOT,
                  summary_path, replay.OUTPUT / "input_manifest.json", root / "receipt.json", root / "archive_receipt.json"])
    files.update(root / f"{name}.csv.gz" for name in archives)
    identities = {str(path): runner._file_identity(path) for path in sorted(files)}
    OUTPUT.mkdir(mode=0o700)
    try:
        batch.write_json(OUTPUT / "input_manifest.json", {"source_identities": identities,
                          "evidence_type": "post_failure_descriptive_diagnostics", "dataset_identity": dataset_identity})
        metadata = {cutoff: json.loads((entry["root"] / "metadata.json").read_text()) for cutoff, entry in registry.items()}
        validate_training_statistics(events, metadata, spec, monthly)
        predictions = batch.read_frame(replay.MODEL_OUTPUT / "baseline_event_predictions.csv")
        joined = join_predictions(events, predictions, metadata)
        c = batch.read_frame(root / "model_decisions.csv.gz")
        if len(c) != summary["decision_audit"]["decision_count"] or int(c.skip.sum()) != summary["decision_audit"]["skip_count"]:
            raise RuntimeError("diagnostic_c_decision_inventory_changed")
        paired, drift = path_drift(joined, c, spec["features"])
        groups = [("all", joined), *[(str(year), frame) for year, frame in joined.groupby(joined.decision_date.str[:4])]]
        regressions, actions = [], []
        for period, frame in groups:
            eligible = frame.loc[frame.evaluable]
            actions.append({"period": period, **action_metrics(frame)})
            for target in TARGETS:
                metrics = regression_metrics(eligible[target], eligible[f"pred_{target}"],
                                             eligible[f"baseline_{target}"], eligible[f"scale_{target}"])
                regressions.append({"period": period, "target": target, **metrics})
        frames = {"event_predictions": joined, "regression_metrics": pd.DataFrame(regressions),
                  "action_metrics": pd.DataFrame(actions), "common_path_differences": paired}
        for name, frame in frames.items():
            with (OUTPUT / f"{name}.csv").open("x") as stream:
                frame.to_csv(stream, index=False, float_format="%.17g")
        for path, identity in identities.items():
            if runner._file_identity(path) != identity:
                raise RuntimeError(f"diagnostic_source_changed:{path}")
        runner.validate_current_input_manifest(manifest)
        result = {"stage": "stage010_failure_diagnostics", "status": "passed",
                  "evidence_type": "post_failure_descriptive_diagnostics", "source_count": len(identities),
                  "events": len(joined), "evaluated_events": int(joined.evaluable.sum()),
                  "censored_events": int(joined.label_status.eq("censored").sum()),
                  "untrained_events": int(joined.status.eq("untrained").sum()),
                  "training_statistics_recomputed_months": len(metadata),
                  "regression": regressions[:2], "actions": actions[0], "path_drift": drift,
                  "new_model_fit_count": 0, "new_model_prediction_count": 0, "new_label_count": 0,
                  "new_strategy_replay_count": 0, "reviewer_started": False,
                  "candidate_primary_gate_passed": summary["comparison"]["primary_gate_passed"],
                  "output_identities": {f"{name}.csv": runner._file_identity(OUTPUT / f"{name}.csv") for name in frames}}
        batch.write_json(OUTPUT / "summary.json", result)
        print(json.dumps(result, allow_nan=False), flush=True)
    except BaseException as exc:
        batch.write_json(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    run()
