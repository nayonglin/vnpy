from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage006_prefix_equivalence"
END = "2022-03-15"
OUTPUT = ROOT / "artifacts" / STAGE
REFERENCE = ROOT / "artifacts/stage004_counterfactual_validation"
FREEZE = ROOT / "stages/20260905_stage006_input_contract_freeze.json"
CONTRACT = ROOT / "stages/20260905_2012_stage006_prefix_equivalence_contract.md"


def load_base():
    path = ROOT / "tools/stage004_counterfactual_validation.py"
    spec = importlib.util.spec_from_file_location("stage006_base", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_inputs():
    base = load_base()
    files = base.collect_inputs()
    files.update({
        "stage005_runner": ROOT / "tools/stage005_event_lifecycle_audit.py",
        "stage005_tests": ROOT / "tests/test_stage005_event_lifecycle_audit.py",
        "stage005_contract": ROOT / "stages/20260905_2007_stage005_lifecycle_audit_contract.md",
        "stage005_record": ROOT / "stages/20260905_2010_stage005_lifecycle_audit_pass.md",
        "stage005_summary": ROOT / "artifacts/stage005_event_lifecycle_audit/summary.json",
        "stage005_lifecycles": ROOT / "artifacts/stage005_event_lifecycle_audit/event_lifecycles.csv",
        "stage004b_runner": ROOT / "tools/stage004b_frozen_artifact_analysis.py",
        "stage004b_tests": ROOT / "tests/test_stage004b_frozen_artifact_analysis.py",
        "stage004b_contract": ROOT / "stages/20260905_stage004b_readonly_analysis_contract.md",
        "stage004b_summary": ROOT / "artifacts/stage004b_frozen_artifact_analysis/summary.json",
        "stage004_record": ROOT / "stages/20260905_1959_stage004_counterfactual_validation_result.md",
        "stage006_runner": Path(__file__).resolve(),
        "stage006_tests": ROOT / "tests/test_stage006_prefix_equivalence.py",
        "stage006_contract": CONTRACT,
        "stage004_input_manifest": REFERENCE / "input_manifest.json",
        "stage004_failure": REFERENCE / "failure.json",
        "stage004_target": REFERENCE / "target.json",
        "stage004_claim": ROOT / "stages/20260905_stage004_execution_state/claim.json",
        "stage004_freeze": ROOT / "stages/20260905_stage004_input_contract_freeze.json",
    })
    for arm in ("A", "S"):
        root = REFERENCE / "workers" / arm
        files[f"stage004_{arm}_receipt"] = root / "receipt.json"
        for name in base.FRAME_NAMES:
            files[f"stage004_{arm}_{name}"] = root / f"{name}.csv"
    if len(files) != 1516 or any(path.is_symlink() or not path.is_file() for path in files.values()):
        raise RuntimeError(f"stage006_inputs_invalid:{len(files)}")
    return dict(sorted(files.items()))


def configured():
    base = load_base()
    runner = base.support()
    runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = 1516
    original_v1 = runner.load_v1_runner

    def short_v1():
        v1 = original_v1()
        v1.END = v1.pd.Timestamp(END)
        return v1

    runner.load_v1_runner = short_v1
    base.support = lambda: runner
    return base, runner


def compare_prefix(reference, observed, date_column, end):
    import pandas as pd

    expected = reference[reference[date_column].astype(str).str[:10].le(end)]
    pd.testing.assert_frame_equal(expected.reset_index(drop=True), observed.reset_index(drop=True),
                                  check_dtype=False, check_exact=True)


def file_identity(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest.hexdigest()}


def archive_csv(path, identity):
    before = file_identity(path)
    if any(before[key] != identity[key] for key in ("size", "sha256")):
        raise RuntimeError("archive_source_identity_mismatch")
    archive = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as source, archive.open("xb") as destination:
        with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as zipped:
            shutil.copyfileobj(source, zipped)
    digest = hashlib.sha256()
    size = 0
    with gzip.open(archive, "rb") as restored:
        for chunk in iter(lambda: restored.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    if size != before["size"] or digest.hexdigest() != before["sha256"]:
        raise RuntimeError("archive_round_trip_failed")
    receipt = {"archive": file_identity(archive), "raw_size": size, "raw_sha256": digest.hexdigest()}
    path.unlink()
    return receipt


def run_parent():
    from concurrent.futures import ThreadPoolExecutor

    base, runner = configured()
    if OUTPUT.exists():
        raise RuntimeError("stage006_output_already_exists")
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    qualified = json.loads((ROOT / "artifacts/stage005_event_lifecycle_audit/summary.json").read_text())
    if qualified["status"] != "passed" or not qualified["label_batch_qualified"]:
        raise RuntimeError("lifecycle_not_qualified")
    runner.claim_execution(ROOT / "stages/20260905_stage006_execution_state/claim.json", manifest)
    OUTPUT.mkdir(mode=0o700)
    runner._write_json_exclusive(OUTPUT / "input_manifest.json", manifest)
    preflight = runner.load_metadata_preflight_module().load_preflight_module()
    paths_by_arm = {}
    try:
        for arm in ("A", "S"):
            database = manifest["files"]["source_database"]
            paths = runner.prepare_stage002_worker_root(OUTPUT / "workers" / arm,
                source_database=Path(database["path"]), expected_database_sha256=database["sha256"])
            preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
            paths_by_arm[arm] = paths

        def run_one(arm):
            paths = paths_by_arm[arm]
            command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]), str(Path(sys.executable).resolve()),
                "-I", "-S", "-B", str(Path(__file__).resolve()), "--worker", "--arm", arm,
                "--worker-root", str(paths["worker_root"]), "--manifest", str(OUTPUT / "input_manifest.json")]
            started = time.monotonic()
            with paths["log"].open("wb") as log:
                completed = subprocess.run(command, cwd=paths["runtime"],
                    env=preflight.expected_worker_environment(paths["runtime"]), stdout=log, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise RuntimeError(f"prefix_worker_failed:{arm}:{paths['log']}")
            print(json.dumps({"arm": arm, "status": "completed", "seconds": time.monotonic() - started}), flush=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_one, arm) for arm in ("A", "S")]
            for future in futures:
                future.result()
        results = {}
        columns = {"daily": "date", "trades": "datetime", "positions": "date", "entry_candidates": "datetime",
                   "entry_risk": "datetime", "stop_retry_events": "datetime", "root_features": "decision_datetime"}
        for arm in ("A", "S"):
            paths = paths_by_arm[arm]
            receipt = json.loads(paths["receipt"].read_text())
            if (receipt["status"] != "passed" or receipt["stage"] != STAGE or receipt["arm"] != arm
                    or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
                    or receipt["formal_replay_call_count"] != 1 or any(receipt["sensitive_counters"].values())
                    or receipt["network_connection_attempt_count"] != 0):
                raise RuntimeError("prefix_worker_receipt_invalid")
            frames = base.read_frames(paths["worker_root"])
            reference = base.read_frames(REFERENCE / "workers" / arm)
            for name, column in columns.items():
                observed = runner._file_identity(paths["worker_root"] / f"{name}.csv")
                if observed != receipt["frames"][name]:
                    raise RuntimeError(f"prefix_frame_identity_mismatch:{arm}:{name}")
                compare_prefix(reference[name], frames[name], column, END)
            if frames["daily"].date.max() != END:
                raise RuntimeError("prefix_horizon_mismatch")
            results[arm] = {"receipt": receipt, "daily": frames["daily"]}
            del frames, reference
        if results["A"]["receipt"]["pid"] == results["S"]["receipt"]["pid"]:
            raise RuntimeError("workers_not_distinct")
        target = base.earliest_target()
        marginal = base.account_marginal(results["A"]["daily"], results["S"]["daily"], target["decision_date"], END,
                                         results["S"]["receipt"]["audit"]["pre_event_equity"])
        expected = json.loads((ROOT / "artifacts/stage004b_frozen_artifact_analysis/summary.json").read_text())["marginal"]
        if marginal != expected:
            raise RuntimeError("marginal_prefix_mismatch")
        archives = {}
        for arm, paths in paths_by_arm.items():
            receipt = results[arm]["receipt"]
            archives[arm] = {name: archive_csv(paths["worker_root"] / f"{name}.csv", identity)
                             for name, identity in receipt["frames"].items()}
            runner._write_json_exclusive(paths["worker_root"] / "archive_receipt.json", archives[arm])
            shutil.rmtree(paths["runtime"])
        runner.validate_current_input_manifest(manifest)
        summary = {"stage": STAGE, "status": "passed", "execution_end": END, "prefix_tables_equal": 14,
                   "marginal_equal": True, "marginal": marginal, "source_file_contract_sha256": manifest["file_contract_sha256"],
                   "metrics": {arm: result["receipt"]["metrics"] for arm, result in results.items()},
                   "archives": archives, "formal_replay_call_count": 2, "model_fit_count": 0,
                   "additional_label_count": 0, "reviewer_started": False}
        runner._write_json_exclusive(OUTPUT / "summary.json", summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "archives"}), flush=True)
    except BaseException as exc:
        for paths in paths_by_arm.values():
            if paths["runtime"].exists():
                shutil.rmtree(paths["runtime"])
        runner._write_json_exclusive(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--arm", choices=("A", "S"))
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.freeze:
        _, runner = configured()
        manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        payload = {key: manifest[key] for key in ("schema_version", "stage", "line_id", "input_file_count",
                   "input_logical_key_sha256", "file_contract_sha256", "runtime_contract_sha256")}
        payload["execution_authorized"] = True
        runner._write_json_exclusive(FREEZE, payload)
        print(json.dumps(payload), flush=True)
    elif args.run:
        run_parent()
    else:
        base, _ = configured()
        base.run_worker(args)


if __name__ == "__main__":
    main()
