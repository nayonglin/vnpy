from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import math
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage005_label_collection"
CONTRACT = ROOT / "stages/20260905_2058_stage005_label_collection_contract.md"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify_identity(path, identity):
    if Path(path).stat().st_size != identity["size"] or digest(path) != identity["sha256"]:
        raise RuntimeError(f"source_changed:{path}")


def verify_archive(path, identity):
    if (Path(path).stat().st_size != identity["archive"]["size"]
            or digest(path) != identity["archive"]["sha256"]):
        raise RuntimeError(f"archive_changed:{path}")
    value, size = hashlib.sha256(), 0
    with gzip.open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
            size += len(block)
    if size != identity["raw_size"] or value.hexdigest() != identity["raw_sha256"]:
        raise RuntimeError(f"decoded_archive_changed:{path}")


def label_rows(plan, labels):
    events = [*plan["jobs"], *plan["censored"]]
    ids = [event["event_id"] for event in events]
    closed = {event["event_id"] for event in plan["jobs"]}
    if len(ids) != len(set(ids)) or not set(labels).issubset(closed):
        raise RuntimeError("label_inventory_invalid")
    rows = []
    for event in events:
        event_id = event["event_id"]
        label = labels.get(event_id)
        row = {"event_id": event_id, "lifecycle_status": event["status"], "label_end_date": event["end_date"],
               "label_status": "censored" if event_id not in closed else "pending",
               "return_marginal": None, "drawdown_marginal": None}
        if label is not None:
            if label["event_id"] != event_id or label["status"] != "passed":
                raise RuntimeError("label_inventory_invalid")
            for name in ("return_marginal", "drawdown_marginal"):
                value = label.get("marginal", {}).get(name)
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise RuntimeError(f"invalid_marginal:{event_id}:{name}")
                row[name] = value
            row["label_status"] = "verified"
        rows.append(row)
    return rows, set(labels) == closed


def normalized_views(batch, root, label, raw_daily, trades, reference, end_date):
    receipt_path = root / "normalization_receipt.json"
    if (digest(receipt_path) != label["analysis_normalization_sha256"]
            or digest(ROOT / "tools/stage004b_zero_trade_analysis.py") != label["analysis_tool_sha256"]):
        raise RuntimeError("normalization_identity_changed")
    evidence = json.loads(receipt_path.read_text())
    if (evidence["status"] != "passed" or evidence["event_id"] != label["event_id"]
            or evidence["new_replay_count"] != 0):
        raise RuntimeError("normalization_receipt_invalid")
    for path, identity in evidence["source_identities"].items():
        verify_identity(path, identity)
    for name in ("normalized_daily", "normalized_positions"):
        verify_archive(root / f"{name}.csv.gz", evidence[name])
    normalizer = batch.load("collection_zero_view", ROOT / "tools/stage004b_zero_trade_analysis.py")
    if label["event_id"] != normalizer.EVENT_ID:
        raise RuntimeError("normalization_event_not_authorized")
    positions = batch.read_frame(root / "positions.csv.gz")
    dates = reference.loc[reference.date.le(end_date), "date"].tolist()
    daily = normalizer.normalize_zero_trade(raw_daily, positions, trades, dates, reference.columns.tolist())
    normalized_positions = normalizer.normalize_zero_positions(positions)
    batch.frame_equal(daily, batch.read_frame(root / "normalized_daily.csv.gz"))
    batch.frame_equal(normalized_positions, batch.read_frame(root / "normalized_positions.csv.gz"))
    return daily


def verify_job(batch, base, job, manifest, reference):
    root = batch.OUTPUT / "jobs" / job["event_id"]
    label = batch.verify_completed(job, root, manifest)
    if (label["lifecycle_status"] != job["status"] or label["pre_target_equal"] is not True
            or label["target_features_exact"] is not True):
        raise RuntimeError("label_validation_flags_invalid")
    for name, identity in json.loads((root / "archive_receipt.json").read_text()).items():
        verify_archive(root / f"{name}.csv.gz", identity)
    daily = batch.read_frame(root / "daily.csv.gz")
    trades = batch.read_frame(root / "trades.csv.gz")
    if "analysis_normalization_sha256" in label:
        daily = normalized_views(batch, root, label, daily, trades, reference["daily"], job["end_date"])
    elif (root / "normalization_receipt.json").exists():
        raise RuntimeError("unbound_normalization_receipt")
    batch.validate_daily_calendar(reference["daily"], daily, job["end_date"])
    receipt = json.loads((root / "receipt.json").read_text())
    marginal = base.account_marginal(reference["daily"], daily, job["target"]["decision_date"],
                                    job["end_date"], receipt["audit"]["pre_event_equity"])
    a_daily = reference["daily"][reference["daily"].date.le(job["end_date"])]
    a_trades = reference["trades"][reference["trades"].date.le(job["end_date"])]
    if (marginal != label["marginal"] or base.equity_metrics(daily, trades) != label["S_metrics"]
            or base.equity_metrics(a_daily, a_trades) != label["A_metrics"]):
        raise RuntimeError(f"label_recomputation_mismatch:{job['event_id']}")
    paths = [root / name for name in ("label.json", "receipt.json", "archive_receipt.json")]
    if "analysis_normalization_sha256" in label:
        paths.append(root / "normalization_receipt.json")
    return label, paths


def main():
    import pandas as pd

    spec = importlib.util.spec_from_file_location("collection_batch", ROOT / "tools/stage004_label_batch.py")
    batch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(batch)
    # Share the batch lock so a snapshot cannot race an incomplete job publication.
    lock = batch.OUTPUT / "run.lock"
    with lock.open("x") as stream:
        import os
        json.dump({"pid": os.getpid(), "mode": STAGE}, stream)
    try:
        base, runner = batch.configured()
        manifest = json.loads((batch.OUTPUT / "input_manifest.json").read_text())
        runner.validate_current_input_manifest(manifest)
        plan = batch.read_plan()
        if digest(batch.FEATURES) != plan["features_sha256"] or digest(batch.LIFECYCLES) != plan["lifecycles_sha256"]:
            raise RuntimeError("feature_or_lifecycle_changed")
        receipt = json.loads((batch.REFERENCE / "receipt.json").read_text())
        reference = {}
        for name in ("daily", "trades"):
            path = batch.REFERENCE / f"{name}.csv"
            verify_identity(path, receipt["frames"][name])
            reference[name] = batch.read_frame(path)
        labels, metrics, sources = {}, [], [Path(__file__).resolve(), CONTRACT,
            ROOT / "tests/test_stage005_label_collection.py", batch.PLAN, batch.SPEC,
            batch.FREEZE, batch.FEATURES, batch.LIFECYCLES, batch.OUTPUT / "input_manifest.json",
            batch.REFERENCE / "receipt.json"]
        unfinished = []
        planned_ids = {job["event_id"] for job in plan["jobs"]}
        if any(path.name not in planned_ids for path in (batch.OUTPUT / "jobs").iterdir()):
            raise RuntimeError("unexpected_job_directory")
        for job in plan["jobs"]:
            root = batch.OUTPUT / "jobs" / job["event_id"]
            if not (root / "label.json").exists():
                if root.exists():
                    unfinished.append(job["event_id"])
                continue
            label, paths = verify_job(batch, base, job, manifest, reference)
            labels[job["event_id"]] = label
            sources.extend(paths)
            metrics.append({"event_id": job["event_id"], "decision_date": job["target"]["decision_date"],
                            "end_date": job["end_date"], "candidate_index": job["target"]["candidate_index"],
                            "product_vt_symbol": job["target"]["product_vt_symbol"],
                            **{f"{arm}_{key}": value for arm in ("A", "S") for key, value in label[f"{arm}_metrics"].items()}})
        rows, complete = label_rows(plan, labels)
        features = batch.read_frame(batch.FEATURES)
        if set(features.event_id) != {row["event_id"] for row in rows}:
            raise RuntimeError("feature_inventory_mismatch")
        dataset = features.merge(pd.DataFrame(rows), on="event_id", validate="one_to_one")
        dataset = dataset.sort_values(["decision_date", "candidate_index"], kind="stable")
        runner.validate_current_input_manifest(manifest)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = ROOT / "artifacts" / STAGE / stamp
        output.mkdir(parents=True, exist_ok=False)
        with (output / "events.csv").open("x") as stream:
            dataset.to_csv(stream, index=False, float_format="%.17g")
        with (output / "counterfactual_metrics.csv").open("x") as stream:
            pd.DataFrame(metrics).to_csv(stream, index=False, float_format="%.17g")
        summary = {"stage": STAGE, "status": "passed", "completed": len(labels), "planned": len(plan["jobs"]),
                   "pending": len(plan["jobs"]) - len(labels), "censored": len(plan["censored"]),
                   "unfinished_job_ids": unfinished, "training_ready": complete and not unfinished,
                   "marginal_recomputation_mismatch_count": 0, "archive_decode_mismatch_count": 0,
                   "normalization_recomputed_count": sum("analysis_normalization_sha256" in row for row in labels.values()),
                   "model_fit_count": 0, "new_replay_count": 0, "reviewer_started": False,
                   "source_identities": {str(path): runner._file_identity(path) for path in sources},
                   "output_identities": {name: runner._file_identity(output / name) for name in ("events.csv", "counterfactual_metrics.csv")}}
        batch.write_json(output / "summary.json", summary)
        print(json.dumps({key: value for key, value in summary.items() if key not in ("source_identities", "output_identities")}), flush=True)
        print(str(output), flush=True)
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
