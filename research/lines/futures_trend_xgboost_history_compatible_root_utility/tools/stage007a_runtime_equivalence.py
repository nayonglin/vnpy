from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage007a_runtime_equivalence"
OUTPUT = ROOT / "artifacts" / STAGE
FREEZE = ROOT / "stages/stage007a_input_freeze.json"
CONTRACT = ROOT / "stages/20260905_2123_stage007a_equivalence_contract.md"
INPUT_COUNT = 1517


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def batch_module():
    return load("equivalence_batch", ROOT / "tools/stage004_label_batch.py")


def bridge_job():
    plan = batch_module().read_plan()
    return next(job for job in plan["jobs"] if job["event_id"] == plan["bridge_event_id"])


def collect_inputs():
    files = batch_module().collect_inputs()
    files.update({"runtime_equivalence_runner": Path(__file__).resolve(),
                  "runtime_equivalence_tests": ROOT / "tests/test_stage007a_runtime_equivalence.py",
                  "runtime_equivalence_contract": CONTRACT,
                  "runtime_gate": ROOT / "tools/stage007_runtime_gate.py",
                  "runtime_gate_tests": ROOT / "tests/test_stage007_runtime_gate.py",
                  "runtime_gate_contract": ROOT / "stages/20260905_2119_stage007_runtime_gate_contract.md"})
    return dict(sorted(files.items()))


def configured(arm="A0"):
    batch = batch_module()
    job = bridge_job()
    base, runner = batch.configured(job if arm == "S" else None)
    base.STAGE = runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = INPUT_COUNT
    base.earliest_target = lambda: job["target"]

    @contextmanager
    def intervention(strategy_class, target):
        gate = load("equivalence_gate", ROOT / "tools/stage007_runtime_gate.py")
        def decide(self):
            if target is None:
                return False
            row = self.entry_candidate_snapshots[-1]
            if row["product_vt_symbol"] != target["product_vt_symbol"] or row["datetime"].isoformat() != target["decision_datetime"]:
                return False
            h = batch.load_history()
            features = h.build_features(h.pd.DataFrame([dict(row)]), target).iloc[0]
            if (features.event_id != target["event_id"] or int(row["candidate_index"]) != target["candidate_index"]
                    or any(float(features[name]) != float(target[name]) for name in h.FEATURES)
                    or audit["verified_snapshot_count"] != 0):
                raise RuntimeError("runtime_bridge_target_changed")
            audit["verified_snapshot_count"] += 1
            audit["pre_event_equity"] = float(row["estimated_equity"])
            row.update(candidate_status="skipped", skip_reason="research_frozen_root_skip", is_opened=0)
            return True
        with gate.install_gate(strategy_class, decide) as audit:
            audit.update(target=target, verified_snapshot_count=0)
            yield audit
    base.intervention = intervention
    return base, runner


def require_frame_equivalence(expected, observed):
    import pandas as pd
    if set(expected) != set(observed):
        raise RuntimeError("equivalence_frame_inventory_mismatch")
    for name in expected:
        pd.testing.assert_frame_equal(expected[name].reset_index(drop=True), observed[name].reset_index(drop=True),
                                      check_dtype=False, check_exact=True, obj=name)


def expected_frames(arm, formal):
    batch = batch_module()
    if arm == "S":
        job = bridge_job()
        root = batch.OUTPUT / "jobs" / job["event_id"]
        manifest = json.loads((batch.OUTPUT / "input_manifest.json").read_text())
        batch.verify_completed(job, root, manifest)
        return {name: batch.read_frame(root / f"{name}.csv.gz") for name in configured()[0].FRAME_NAMES}
    base, runner = configured()
    receipt = json.loads((batch.REFERENCE / "receipt.json").read_text())
    frames = {}
    for name in base.FRAME_NAMES:
        if name == "root_features":
            continue
        path = batch.REFERENCE / f"{name}.csv"
        if runner._file_identity(path) != receipt["frames"][name]:
            raise RuntimeError("frozen_A_frame_changed")
        frames[name] = batch.read_frame(path)
    frames["root_features"] = batch.load_history().build_features(frames["entry_candidates"], formal)
    return frames


def run_parent():
    batch = batch_module()
    _, runner = configured()
    if OUTPUT.exists():
        raise RuntimeError("runtime_equivalence_already_exists")
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise RuntimeError("runtime_equivalence_disk_reserve")
    lock = batch.OUTPUT / "run.lock"
    with lock.open("x") as stream:
        json.dump({"pid": os.getpid(), "mode": STAGE}, stream)
    results = {}
    try:
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / "input_manifest.json", manifest)
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        archiver = batch.load("equivalence_archive", batch.V4 / "tools/stage006_prefix_equivalence.py")
        for arm in ("A0", "S"):
            started = time.monotonic()
            root = OUTPUT / "workers" / arm
            database = manifest["files"]["source_database"]
            paths = runner.prepare_stage002_worker_root(root, source_database=Path(database["path"]),
                                                       expected_database_sha256=database["sha256"])
            try:
                preflight.write_sandbox_profile(paths["profile"], root)
                command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]), str(Path(sys.executable).resolve()),
                           "-I", "-S", "-B", str(Path(__file__).resolve()), "--worker", "--arm", arm,
                           "--worker-root", str(root), "--manifest", str(OUTPUT / "input_manifest.json")]
                with paths["log"].open("wb") as stream:
                    completed = subprocess.run(command, cwd=paths["runtime"],
                        env=preflight.expected_worker_environment(paths["runtime"]), stdout=stream, stderr=subprocess.STDOUT)
                if completed.returncode:
                    raise RuntimeError(f"runtime_worker_failed:{arm}:{completed.returncode}")
                base, _ = configured(arm)
                receipt = json.loads(paths["receipt"].read_text())
                if (receipt["status"] != "passed" or receipt["arm"] != arm or receipt["stage"] != STAGE
                        or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
                        or receipt["formal_identity"] != manifest["formal_identity"]
                        or receipt["formal_replay_call_count"] != 1 or any(receipt["sensitive_counters"].values())
                        or receipt["network_connection_attempt_count"] != 0):
                    raise RuntimeError("runtime_receipt_invalid")
                for name, identity in receipt["frames"].items():
                    if runner._file_identity(root / f"{name}.csv") != identity:
                        raise RuntimeError("runtime_output_changed")
                observed = base.read_frames(root)
                expected = expected_frames(arm, receipt["formal_identity"])
                require_frame_equivalence(expected, observed)
                if receipt["metrics"] != base.equity_metrics(expected["daily"], expected["trades"]):
                    raise RuntimeError("runtime_metrics_changed")
                expected_skips = int(arm == "S")
                if (receipt["audit"]["skip_count"] != expected_skips
                        or receipt["audit"]["verified_snapshot_count"] != expected_skips):
                    raise RuntimeError("runtime_skip_count_changed")
                archives = {name: archiver.archive_csv(root / f"{name}.csv", identity) for name, identity in receipt["frames"].items()}
                batch.write_json(root / "archive_receipt.json", archives)
                results[arm] = {"status": "passed", "all_seven_frames_exact": True, "metrics": receipt["metrics"],
                                "audit": receipt["audit"], "seconds": time.monotonic() - started,
                                "receipt_sha256": batch.digest(paths["receipt"])}
                print(json.dumps({"arm": arm, "status": "passed", "seconds": results[arm]["seconds"]}), flush=True)
                del observed, expected
            finally:
                if paths["runtime"].exists():
                    shutil.rmtree(paths["runtime"])
        runner.validate_current_input_manifest(manifest)
        summary = {"stage": STAGE, "status": "passed", "results": results, "formal_replay_call_count": 2,
                   "new_training_label_count": 0, "historical_model_fit_count": 0, "reviewer_started": False,
                   "new_model_strategy_candidate": False, "file_contract_sha256": manifest["file_contract_sha256"]}
        batch.write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / "failure.json").exists():
            batch.write_json(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "results": results,
                                                      "traceback": traceback.format_exc()})
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--arm", choices=["A0", "S"])
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.freeze:
        batch = batch_module()
        _, runner = configured()
        manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        batch.verify_baseline_inputs(manifest)
        payload = {key: manifest[key] for key in ("schema_version", "stage", "line_id", "input_file_count",
                   "input_logical_key_sha256", "file_contract_sha256", "runtime_contract_sha256")}
        payload["execution_authorized"] = True
        batch.write_json(FREEZE, payload)
        print(json.dumps(payload), flush=True)
    elif args.worker:
        configured(args.arm)[0].run_worker(args)
    else:
        run_parent()


if __name__ == "__main__":
    main()
