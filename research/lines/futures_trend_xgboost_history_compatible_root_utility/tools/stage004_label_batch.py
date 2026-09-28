from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4"
STAGE = "stage004_label_batch"
OUTPUT = ROOT / "artifacts" / STAGE
PLAN = ROOT / "stages/stage004_job_plan.json"
SPEC = ROOT / "stages/stage004_model_spec.json"
CONTRACT = ROOT / "stages/20260905_2042_stage004_label_batch_contract.md"
FREEZE = ROOT / "stages/stage004_input_freeze.json"
FEATURES = ROOT / "artifacts/stage001_history_qualification/event_features.csv"
LIFECYCLES = ROOT / "artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv"
REFERENCE = V4 / "artifacts/stage004_counterfactual_validation/workers/A"
BRIDGE = V4 / "artifacts/stage004b_frozen_artifact_analysis/summary.json"
INPUT_COUNT = 1511
GIB = 1024 ** 3
WORKER_SPACE = 384 * 1024 ** 2


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_history():
    return load("batch_history", ROOT / "tools/stage001_history_qualification.py")


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def write_json(path, payload):
    with Path(path).open("x") as stream:
        json.dump(payload, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)


def partition_events(rows):
    jobs, censored = [], []
    event_ids, candidate_ids = set(), set()
    for row in sorted(rows, key=lambda item: (item["decision_date"], item["candidate_index"])):
        if (row["event_id"] in event_ids or row["candidate_index"] in candidate_ids
                or row["product_vt_symbol"] == "fu.SHFE"):
            raise RuntimeError("event_identity_invalid")
        event_ids.add(row["event_id"])
        candidate_ids.add(row["candidate_index"])
        if row["status"] in ("mature", "mature_cancelled_unfilled"):
            if not row["end_date"] or row["end_date"] < row["decision_date"]:
                raise RuntimeError("event_endpoint_invalid")
            jobs.append(row)
        elif row["status"] in ("right_censored_open", "right_censored_pending_entry"):
            censored.append(row)
        else:
            raise RuntimeError("event_status_unresolved")
    return jobs, censored


def prepare_plan():
    import pandas as pd

    if PLAN.exists():
        raise RuntimeError("plan_already_exists")
    summary = json.loads((LIFECYCLES.parent / "summary.json").read_text())
    feature_summary = json.loads((FEATURES.parent / "summary.json").read_text())
    if (summary["status"] != "passed" or not summary["eligible_for_label_preregistration"]
            or digest(LIFECYCLES) != summary["event_lifecycle_identity"]["sha256"]
            or digest(FEATURES) != feature_summary["output_identities"]["event_features"]["sha256"]):
        raise RuntimeError("history_source_not_qualified")
    h = load_history()
    features = pd.read_csv(FEATURES, float_precision="round_trip").set_index("event_id", drop=False)
    events = pd.read_csv(LIFECYCLES, float_precision="round_trip")
    records = json.loads(events.to_json(orient="records"))
    jobs, censored = partition_events(records)
    if len(jobs) != 274 or len(censored) != 2 or len(features) != 276:
        raise RuntimeError("qualified_event_count_changed")
    planned = []
    for row in jobs:
        target = features.loc[row["event_id"]].to_dict()
        if h.upstream._event_id(target, target) != target["event_id"]:
            raise RuntimeError("event_id_hash_mismatch")
        planned.append({"event_id": row["event_id"], "status": row["status"], "end_date": row["end_date"], "target": target})
    dynamic = pd.read_csv(REFERENCE / "root_features.csv").sort_values(["decision_datetime", "event_id"], kind="stable")
    first = [job["event_id"] for job in planned if job["status"] == "mature"][:3]
    cancelled = [job["event_id"] for job in planned if job["status"] == "mature_cancelled_unfilled"]
    bridge_id = str(dynamic.iloc[0].event_id)
    canary = list(dict.fromkeys([*first, *cancelled, bridge_id]))
    if len(canary) != 5 or len(cancelled) != 1:
        raise RuntimeError("canary_selection_invalid")
    plan = {"schema_version": 1, "stage": STAGE, "line_id": ROOT.name, "jobs": planned, "censored": censored,
            "canary_event_ids": canary, "bridge_event_id": bridge_id, "features_sha256": digest(FEATURES),
            "lifecycles_sha256": digest(LIFECYCLES), "model_spec_sha256": digest(SPEC)}
    write_json(PLAN, plan)
    print(json.dumps({"jobs": len(planned), "censored": len(censored), "canary": canary, "plan_sha256": digest(PLAN)}), flush=True)


def read_plan():
    plan = json.loads(PLAN.read_text())
    if (plan["stage"] != STAGE or plan["line_id"] != ROOT.name or len(plan["jobs"]) != 274
            or digest(SPEC) != plan["model_spec_sha256"]):
        raise RuntimeError("plan_invalid")
    return plan


def collect_inputs():
    source = load("batch_source_inputs", ROOT / "tools/stage002_unfilled_trace.py")
    files = source.collect_inputs()
    # LINE is a mutable status index; the immutable experiment contract replaces it.
    files.pop("history_line")
    files.update({"batch_runner": Path(__file__).resolve(), "batch_tests": ROOT / "tests/test_stage004_label_batch.py",
                  "batch_contract": CONTRACT, "batch_model_spec": SPEC, "batch_job_plan": PLAN,
                  "cancelled_runner": ROOT / "tools/stage003_cancelled_lifecycle.py",
                  "cancelled_tests": ROOT / "tests/test_stage003_cancelled_lifecycle.py",
                  "cancelled_summary": LIFECYCLES.parent / "summary.json", "cancelled_lifecycles": LIFECYCLES,
                  "baseline_input_manifest": REFERENCE.parents[1] / "input_manifest.json", "bridge_summary": BRIDGE})
    return dict(sorted(files.items()))


def feature_adapter(candidates, eligibility, identity):
    h = load_history()
    selected = candidates.is_opened.eq(1) & candidates.entry_context.eq("flat_entry") & candidates.candidate_status.eq("opened") & candidates.product_vt_symbol.ne("fu.SHFE")
    if not selected.any():
        return h.pd.DataFrame(columns=[*h.ID_COLUMNS, *h.FEATURES])
    return h.build_features(candidates, identity)


def configured(job=None):
    base = load("batch_worker_base", V4 / "tools/stage004_counterfactual_validation.py")
    runner = base.support()
    base.STAGE = runner.STAGE = STAGE
    runner.LINE_ID = ROOT.name
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = INPUT_COUNT
    original_v1 = runner.load_v1_runner
    def local_v1():
        v1 = original_v1()
        if job:
            v1.END = v1.pd.Timestamp(job["end_date"])
        return v1
    runner.load_v1_runner = local_v1
    runner.load_feature_module = lambda: SimpleNamespace(build_formal_root_event_features=feature_adapter)
    if job:
        base.earliest_target = lambda: job["target"]
    base.support = lambda: runner
    return base, runner


def verify_baseline_inputs(manifest):
    baseline = json.loads((REFERENCE.parents[1] / "input_manifest.json").read_text())
    current = {value["path"]: value for value in manifest["files"].values()}
    checked = 0
    for identity in baseline["files"].values():
        if Path(identity["path"]).suffix == ".md":
            continue
        value = current.get(identity["path"])
        if value is None or (value["size"], value["sha256"]) != (identity["size"], identity["sha256"]):
            raise RuntimeError(f"baseline_scientific_input_drift:{identity['path']}")
        checked += 1
    if manifest["formal_identity"] != baseline["formal_identity"]:
        raise RuntimeError("baseline_formal_identity_drift")
    return checked


def validate_daily_calendar(reference, observed, end):
    expected = reference[reference.date.le(end)].date.tolist()
    if not expected or observed.date.tolist() != expected or expected[-1] != end or expected != sorted(set(expected)):
        raise RuntimeError("daily_calendar_mismatch")


def read_frame(path):
    import pandas as pd
    try:
        return pd.read_csv(path, float_precision="round_trip", low_memory=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def frame_equal(left, right):
    import pandas as pd
    if left.empty and right.empty:
        return
    pd.testing.assert_frame_equal(left.reset_index(drop=True), right.reset_index(drop=True), check_dtype=False, check_exact=True)


def validate_job(job, root, manifest, reference):
    import pandas as pd

    base, runner = configured(job)
    receipt = json.loads((root / "receipt.json").read_text())
    if (receipt["status"] != "passed" or receipt["stage"] != STAGE or receipt["arm"] != "S"
            or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
            or receipt["formal_identity"] != manifest["formal_identity"]
            or receipt["formal_replay_call_count"] != 1 or any(receipt["sensitive_counters"].values())
            or receipt["network_connection_attempt_count"] != 0
            or receipt["audit"]["skip_count"] != 1 or receipt["audit"]["verified_snapshot_count"] != 1
            or receipt["audit"]["target"] != job["target"]):
        raise RuntimeError("worker_receipt_invalid")
    frames = {}
    for name, identity in receipt["frames"].items():
        path = root / f"{name}.csv"
        if runner._file_identity(path) != identity:
            raise RuntimeError(f"worker_frame_changed:{name}")
        frames[name] = read_frame(path)
    if set(frames) != set(base.FRAME_NAMES):
        raise RuntimeError("worker_frame_inventory_invalid")
    date = job["target"]["decision_date"]
    validate_daily_calendar(reference["daily"], frames["daily"], job["end_date"])
    for name, column in (("daily", "date"), ("trades", "datetime"), ("positions", "date")):
        a = reference[name]
        a = a[a[column].astype(str).str[:10].lt(date)]
        s = frames[name]
        if not s.empty:
            s = s[s[column].astype(str).str[:10].lt(date)]
        frame_equal(a, s)
    a, s = reference["entry_candidates"], frames["entry_candidates"]
    index = int(job["target"]["candidate_index"])
    frame_equal(a[a.candidate_index.lt(index)], s[s.candidate_index.lt(index)])
    before = a[a.candidate_index.eq(index)].copy()
    after = s[s.candidate_index.eq(index)].copy()
    if (len(before) != 1 or len(after) != 1 or after.iloc[0].candidate_status != "skipped"
            or after.iloc[0].skip_reason != "research_frozen_root_skip" or after.iloc[0].is_opened != 0):
        raise RuntimeError("target_snapshot_invalid")
    for key in ("product_vt_symbol", "contract_vt_symbol", "direction", "signal"):
        if after.iloc[0][key] != job["target"][key]:
            raise RuntimeError("target_identity_mismatch")
    h = load_history()
    after["is_opened"] = 1
    after["candidate_status"] = "opened"
    rebuilt = h.build_features(after, receipt["formal_identity"]).iloc[0]
    if rebuilt.event_id != job["event_id"]:
        raise RuntimeError("target_event_id_mismatch")
    for key in h.FEATURES:
        if float(rebuilt[key]) != float(job["target"][key]):
            raise RuntimeError(f"target_feature_changed:{key}")
    pre_equity = float(before.iloc[0].estimated_equity)
    if pre_equity != receipt["audit"]["pre_event_equity"]:
        raise RuntimeError("pre_event_equity_mismatch")
    marginal = base.account_marginal(reference["daily"], frames["daily"], date, job["end_date"], pre_equity)
    actual_metrics = base.equity_metrics(frames["daily"], frames["trades"])
    if actual_metrics != receipt["metrics"]:
        raise RuntimeError("worker_metric_mismatch")
    plan = read_plan()
    if job["event_id"] == plan["bridge_event_id"] and marginal != json.loads(BRIDGE.read_text())["marginal"]:
        raise RuntimeError("bridge_marginal_mismatch")
    a_daily = reference["daily"][reference["daily"].date.le(job["end_date"])]
    a_trades = reference["trades"][reference["trades"].date.le(job["end_date"])]
    return {"event_id": job["event_id"], "status": "passed", "lifecycle_status": job["status"],
            "marginal": marginal, "A_metrics": base.equity_metrics(a_daily, a_trades), "S_metrics": actual_metrics,
            "plan_sha256": digest(PLAN), "file_contract_sha256": manifest["file_contract_sha256"],
            "receipt_sha256": digest(root / "receipt.json"), "pre_target_equal": True, "target_features_exact": True}


def verify_completed(job, root, manifest):
    label = json.loads((root / "label.json").read_text())
    if (label["status"] != "passed" or label["event_id"] != job["event_id"]
            or label["file_contract_sha256"] != manifest["file_contract_sha256"]
            or label["plan_sha256"] != digest(PLAN) or label["receipt_sha256"] != digest(root / "receipt.json")):
        raise RuntimeError("completed_job_identity_invalid")
    archives = json.loads((root / "archive_receipt.json").read_text())
    receipt = json.loads((root / "receipt.json").read_text())
    if set(archives) != set(receipt["frames"]):
        raise RuntimeError("completed_archive_inventory_invalid")
    for name, item in archives.items():
        if (digest(root / f"{name}.csv.gz") != item["archive"]["sha256"]
                or item["raw_sha256"] != receipt["frames"][name]["sha256"]
                or item["raw_size"] != receipt["frames"][name]["size"]):
            raise RuntimeError("completed_archive_changed")
    return label


def run_batch(mode, limit, workers):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    base, runner = configured()
    plan = read_plan()
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    scientific_count = verify_baseline_inputs(manifest)
    OUTPUT.mkdir(mode=0o700, exist_ok=True)
    manifest_path = OUTPUT / "input_manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text()) != manifest:
            raise RuntimeError("batch_manifest_changed")
    else:
        write_json(manifest_path, manifest)
    lock_path = OUTPUT / "run.lock"
    with lock_path.open("x") as stream:
        json.dump({"pid": os.getpid(), "mode": mode}, stream)
    try:
        completed = {}
        for job in plan["jobs"]:
            root = OUTPUT / "jobs" / job["event_id"]
            if (root / "label.json").exists():
                completed[job["event_id"]] = verify_completed(job, root, manifest)
            elif root.exists():
                raise RuntimeError(f"unfinished_job_requires_inspection:{job['event_id']}")
        canary = set(plan["canary_event_ids"])
        if mode == "next" and not canary.issubset(completed):
            raise RuntimeError("canary_not_complete")
        jobs = [job for job in plan["jobs"] if job["event_id"] not in completed and (mode != "canary" or job["event_id"] in canary)]
        if mode == "next":
            jobs = jobs[:limit]
        if not jobs:
            print(json.dumps({"status": "no_pending_jobs", "completed": len(completed)}), flush=True)
            return
        workers = min(workers, len(jobs), 3)
        if workers < 1 or shutil.disk_usage(ROOT).free < GIB + workers * WORKER_SPACE:
            raise RuntimeError("insufficient_disk_for_batch")
        batches = OUTPUT / "batches"
        batches.mkdir(exist_ok=True)
        batch = batches / f"{len(list(batches.iterdir())) + 1:04d}"
        batch.mkdir(mode=0o700)
        write_json(batch / "selection.json", {"event_ids": [job["event_id"] for job in jobs], "mode": mode,
                   "worker_count": workers, "plan_sha256": digest(PLAN), "scientific_inputs_verified": scientific_count})
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        archiver = load("batch_archiver", V4 / "tools/stage006_prefix_equivalence.py")
        reference = {name: read_frame(REFERENCE / f"{name}.csv") for name in ("daily", "trades", "positions", "entry_candidates")}
        def run_one(job):
            root = OUTPUT / "jobs" / job["event_id"]
            paths = None
            start = time.monotonic()
            try:
                if shutil.disk_usage(ROOT).free < GIB + WORKER_SPACE:
                    raise RuntimeError("disk_reserve_exhausted")
                database = manifest["files"]["source_database"]
                paths = runner.prepare_stage002_worker_root(root, source_database=Path(database["path"]),
                                                           expected_database_sha256=database["sha256"])
                preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
                command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]), str(Path(sys.executable).resolve()),
                           "-I", "-S", "-B", str(Path(__file__).resolve()), "--worker", "--event-id", job["event_id"],
                           "--arm", "S", "--worker-root", str(root), "--manifest", str(manifest_path)]
                with paths["log"].open("wb") as stream:
                    result = subprocess.run(command, cwd=paths["runtime"], env=preflight.expected_worker_environment(paths["runtime"]),
                                            stdout=stream, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f"worker_failed:{result.returncode}")
                label = validate_job(job, root, manifest, reference)
                receipt = json.loads(paths["receipt"].read_text())
                archives = {name: archiver.archive_csv(root / f"{name}.csv", identity) for name, identity in receipt["frames"].items()}
                write_json(root / "archive_receipt.json", archives)
                label["seconds"] = time.monotonic() - start
                write_json(root / "label.json", label)
                print(json.dumps({"event_id": job["event_id"], "candidate_index": job["target"]["candidate_index"],
                                  "status": "passed", "seconds": label["seconds"]}), flush=True)
                return label
            except BaseException as exc:
                if root.exists() and not (root / "failure.json").exists():
                    write_json(root / "failure.json", {"error": str(exc), "traceback": traceback.format_exc()})
                return {"event_id": job["event_id"], "status": "failed", "error": str(exc)}
            finally:
                if paths and paths["runtime"].exists():
                    shutil.rmtree(paths["runtime"])
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run_one, job) for job in jobs]
            for future in as_completed(futures):
                results.append(future.result())
        runner.validate_current_input_manifest(manifest)
        failed = [row for row in results if row["status"] != "passed"]
        summary = {"stage": STAGE, "status": "failed" if failed else "passed", "mode": mode, "selected_count": len(jobs),
                   "passed_count": len(results) - len(failed), "failed": failed,
                   "total_completed_count": len(completed) + len(results) - len(failed), "total_planned_count": len(plan["jobs"]),
                   "plan_sha256": digest(PLAN), "model_fit_count": 0, "reviewer_started": False}
        write_json(batch / "summary.json", summary)
        print(json.dumps(summary), flush=True)
        if failed:
            raise RuntimeError("batch_has_failures")
    finally:
        lock_path.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--canary", action="store_true")
    mode.add_argument("--next", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--event-id")
    parser.add_argument("--arm", choices=["S"])
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare_plan()
    elif args.freeze:
        _, runner = configured()
        manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        count = verify_baseline_inputs(manifest)
        payload = {key: manifest[key] for key in ("schema_version", "stage", "line_id", "input_file_count",
                   "input_logical_key_sha256", "file_contract_sha256", "runtime_contract_sha256")}
        payload["execution_authorized"] = True
        write_json(FREEZE, payload)
        print(json.dumps({**payload, "baseline_scientific_inputs_verified": count}), flush=True)
    elif args.worker:
        selected = [job for job in read_plan()["jobs"] if job["event_id"] == args.event_id]
        if len(selected) != 1:
            raise RuntimeError("worker_job_not_in_plan")
        base, _ = configured(selected[0])
        base.run_worker(args)
    else:
        if args.limit <= 0 or not 1 <= args.workers <= 3:
            raise RuntimeError("invalid_batch_size")
        run_batch("canary" if args.canary else "next", args.limit, args.workers)


if __name__ == "__main__":
    main()
