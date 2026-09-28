from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
STAGE = "stage009_full_path_replay"
OUTPUT = ROOT / "artifacts" / STAGE
MODEL_OUTPUT = ROOT / "artifacts/stage006_monthly_fit"
FREEZE = ROOT / "stages/stage009_input_freeze.json"
CONTRACT = ROOT / "stages/20260905_2208_stage009_full_path_contract.md"
FRAME_NAMES = ("daily", "trades", "positions", "entry_candidates", "entry_risk", "stop_retry_events", "root_features", "model_decisions")


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def catalog():
    spec = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())
    return load("path_model_catalog", "stage008_model_catalog.py").load_catalog(MODEL_OUTPUT, spec)


def qualify_equivalence(root):
    root = Path(root)
    eq = load("path_equivalence_qualification", "stage007a_runtime_equivalence.py")
    batch = eq.batch_module()
    _, runner = eq.configured()
    manifest_path = root / "input_manifest.json"
    runner.validate_current_input_manifest(json.loads(manifest_path.read_text()))
    summary_path = root / "summary.json"
    summary = json.loads(summary_path.read_text())
    if summary["status"] != "passed" or set(summary["results"]) != {"A0", "S"}:
        raise RuntimeError("runtime_equivalence_not_qualified")
    files = [manifest_path, summary_path]
    collector = load("path_equivalence_archives", "stage005_label_collection.py")
    for arm in ("A0", "S"):
        worker = root / "workers" / arm
        receipt_path = worker / "receipt.json"
        result = summary["results"][arm]
        if batch.digest(receipt_path) != result["receipt_sha256"]:
            raise RuntimeError("equivalence_receipt_changed")
        receipt = json.loads(receipt_path.read_text())
        if (not result["all_seven_frames_exact"] or receipt["status"] != "passed" or receipt["arm"] != arm
                or receipt["audit"]["skip_count"] != int(arm == "S")
                or receipt["audit"] != result["audit"] or set(receipt["frames"]) != set(FRAME_NAMES[:-1])):
            raise RuntimeError("equivalence_receipt_invalid")
        archive_path = worker / "archive_receipt.json"
        archives = json.loads(archive_path.read_text())
        if set(archives) != set(receipt["frames"]):
            raise RuntimeError("equivalence_archive_inventory_invalid")
        files.extend([receipt_path, archive_path])
        for name, identity in archives.items():
            if (identity["raw_sha256"] != receipt["frames"][name]["sha256"]
                    or identity["raw_size"] != receipt["frames"][name]["size"]):
                raise RuntimeError("equivalence_archive_receipt_mismatch")
            path = worker / f"{name}.csv.gz"
            collector.verify_archive(path, identity)
            files.append(path)
    return {"files": files, "source_sha256": summary["results"]["A0"]["audit"]["source_sha256"],
            "decoded_archive_count": 14}


def collect_inputs():
    equivalence = load("path_equivalence", "stage007a_runtime_equivalence.py")
    files = equivalence.collect_inputs()
    _, spec, evidence = catalog()
    load("path_campaign", "stage006_training_campaign.py").check_versions(spec)
    files["full_path_contract"] = CONTRACT
    for name in ("stage006_monthly_models", "stage006_training_campaign", "stage008_frozen_inference",
                 "stage008_model_catalog", "stage009_full_path_replay", "stage009_path_validation"):
        files[f"full_path_tool_{name}"] = ROOT / "tools" / f"{name}.py"
        files[f"full_path_test_{name}"] = ROOT / "tests" / f"test_{name}.py"
    files["full_path_inference_plan"] = ROOT / "stages/20260905_2156_stage008_inference_plan.md"
    for index, path in enumerate(qualify_equivalence(equivalence.OUTPUT)["files"]):
        files[f"full_path_equivalence_{index:02d}"] = path
    for index, path in enumerate(evidence["files"]):
        files[f"trained_campaign_{index:04d}"] = path
    _, runner = equivalence.batch_module().configured()
    package = runner.load_metadata_preflight_module().load_preflight_module().python_site_packages() / "xgboost"
    for path in sorted(package.rglob("*.py")):
        files[f"xgboost_source_{path.relative_to(package).as_posix()}"] = path
    for path in sorted((package / "lib").glob("*")):
        if path.is_file():
            files[f"xgboost_native_{path.name}"] = path
    return dict(sorted(files.items()))


def configured(input_count=None):
    batch = load("path_batch", "stage004_label_batch.py")
    base, runner = batch.configured()
    runner.STAGE = base.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = (input_count if input_count is not None
                                        else json.loads(FREEZE.read_text())["input_file_count"])
    return batch, base, runner


def freeze_inputs():
    files = collect_inputs()
    batch, _, runner = configured(len(files))
    manifest = runner.build_input_manifest()
    runner.validate_input_manifest_payload(manifest)
    batch.verify_baseline_inputs(manifest)
    payload = {key: manifest[key] for key in ("schema_version", "stage", "line_id", "input_file_count",
               "input_logical_key_sha256", "file_contract_sha256", "runtime_contract_sha256")}
    payload["execution_authorized"] = True
    batch.write_json(FREEZE, payload)
    print(json.dumps(payload), flush=True)


def inference_guard(preflight, registry, spec, roots, allowed_replays=0):
    batch, base, _ = configured()
    baseline = base.load_stage003()
    monthly = load("path_monthly", "stage006_monthly_models.py")
    factory = load("path_guard", "stage008_frozen_inference.py").frozen_guard_class
    return factory(preflight, baseline, monthly)(roots, registry=registry, spec=spec,
                                                allowed_formal_replay_count=allowed_replays)


def validate_worker_receipt(receipt, manifest, source_sha):
    if (receipt["stage"] != STAGE or receipt["status"] != "passed" or receipt["arm"] != "C"
            or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
            or receipt["formal_identity"] != manifest["formal_identity"]
            or receipt["formal_replay_call_count"] != 1 or receipt["network_connection_attempt_count"] != 0
            or any(receipt["sensitive_counters"].values()) or receipt["baseline_inference"]["load_count"] != 1
            or receipt["release_adapter_call_count"] != 1 or receipt["release_adapter_restored"] is not True
            or set(receipt["frames"]) != set(FRAME_NAMES) or receipt["audit"]["source_sha256"] != source_sha):
        raise RuntimeError("full_path_worker_receipt_invalid")


def run_worker(args):
    # Bootstrap without site imports before the private runtime identity is checked.
    batch = load("path_bootstrap", "stage004_label_batch.py")
    _, runner = batch.configured()
    support = runner.load_metadata_preflight_module()
    preflight = support.load_preflight_module()
    root = args.worker_root.resolve(strict=True)
    runtime = root / "runtime"
    preflight._validate_worker_bootstrap(runtime)
    preflight.prove_external_write_denied(root.parent.parent / "probe_C")
    sys.path.extend([str(preflight.python_site_packages()), str(WORKSPACE)])
    batch, base, runner = configured()
    manifest = json.loads(args.manifest.read_text())
    runner.validate_current_input_manifest(manifest)
    if runner._file_identity(runtime / ".vntrader/database.db")["sha256"] != manifest["files"]["source_database"]["sha256"]:
        raise RuntimeError("database_copy_mismatch")
    registry, spec, _ = catalog()
    attestation = preflight._load_release_attestation(runner.RELEASE_ATTESTATION)
    v1 = runner.load_v1_runner()
    formal = v1._active_formal_identity()
    if formal != manifest["formal_identity"]:
        raise RuntimeError("full_path_formal_identity_mismatch")
    expected = support.validate_frozen_metadata_files(manifest)
    history = batch.load_history()
    gate = load("path_gate", "stage007_runtime_gate.py")
    network = preflight.NetworkBlock()
    guard = inference_guard(preflight, registry, spec, (root,), 1)
    guard.assert_no_sensitive_modules_loaded()
    runner._write_json_exclusive(root / "started.json", {"pid": os.getpid(), "arm": "C", "status": "replaying"})
    with network, guard:
        context, adapter_calls, restored = preflight.import_production_context_with_attestation(attestation)
        candidate = sys.modules[runner.CANDIDATE_MODULE_NAME]
        strategy = context["s901"].s847.QmtRollPortfolioStrategyStage847C9StopRetry
        def feature_builder(snapshot):
            return history.build_features(v1.pd.DataFrame([snapshot]), formal).iloc[0].to_dict()
        decide, records = gate.make_decider(feature_builder, guard.predict_event)
        with support.redirect_metadata_outputs(candidate, root) as targets:
            metadata = context["s901"].s513._metadata()
            restore_trace = v1._install_correlation_trace_instrumentation(strategy)
            try:
                with gate.install_gate(strategy, decide) as audit:
                    daily, raw, engine_spec = context["s901"]._run_live_c9(metadata, v1.START, v1.END)
            finally:
                restore_trace()
            support.verify_derived_outputs(targets, expected)
        if (float(engine_spec.capital.account_capital) != 150000
                or engine_spec.profile != context["live_config"].OFFICIAL_LIVE_PROFILE_NAME):
            raise RuntimeError("full_path_engine_spec_mismatch")
        features = batch.feature_adapter(raw["entry_candidates"], None, formal)
        decisions = v1.pd.DataFrame(records, columns=[*history.ID_COLUMNS, *history.FEATURES,
                  "cutoff", "status", "skip", "return_marginal", "drawdown_marginal"])
        frames = {"daily": daily, "root_features": features, "model_decisions": decisions,
                  **{name: raw[name] for name in base.FRAME_NAMES if name not in {"daily", "root_features"}}}
    if (any(guard.counters.values()) or network.attempts or guard.formal_replay_call_count != 1
            or len(adapter_calls) != 1 or not restored or guard.load_count != 1):
        raise RuntimeError("full_path_worker_safety_failed")
    identities = {}
    for name, frame in frames.items():
        path = root / f"{name}.csv"
        runner._write_bytes_exclusive(path, frame.to_csv(index=False, float_format="%.17g").encode())
        identities[name] = runner._file_identity(path)
    receipt = {"stage": STAGE, "status": "passed", "arm": "C", "pid": os.getpid(),
               "file_contract_sha256": manifest["file_contract_sha256"], "formal_identity": formal,
               "frames": identities, "audit": audit, "metrics": base.equity_metrics(daily, raw["trades"]),
               "baseline_inference": guard.receipt(), "xgboost_inference": guard.xgboost_receipt(),
               "sensitive_counters": guard.counters, "formal_replay_call_count": guard.formal_replay_call_count,
               "network_connection_attempt_count": network.attempts,
               "release_adapter_call_count": len(adapter_calls), "release_adapter_restored": restored}
    runner._write_json_exclusive(root / "receipt.json", receipt)


def run_parent():
    batch, base, runner = configured()
    if OUTPUT.exists():
        raise RuntimeError("full_path_campaign_already_exists")
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    registry, spec, _ = catalog()
    equivalence = load("path_eq_validation", "stage007a_runtime_equivalence.py")
    source_sha = qualify_equivalence(equivalence.OUTPUT)["source_sha256"]
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise RuntimeError("full_path_disk_reserve")
    lock = batch.OUTPUT / "run.lock"
    with lock.open("x") as stream:
        json.dump({"pid": os.getpid(), "mode": STAGE}, stream)
    paths = None
    try:
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / "input_manifest.json", manifest)
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        root = OUTPUT / "workers/C"
        database = manifest["files"]["source_database"]
        paths = runner.prepare_stage002_worker_root(root, source_database=Path(database["path"]),
                                                   expected_database_sha256=database["sha256"])
        preflight.write_sandbox_profile(paths["profile"], root)
        command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]), str(Path(sys.executable).resolve()),
                   "-I", "-S", "-B", str(Path(__file__).resolve()), "--worker", "--worker-root", str(root),
                   "--manifest", str(OUTPUT / "input_manifest.json")]
        with paths["log"].open("wb") as stream:
            result = subprocess.run(command, cwd=paths["runtime"],
                       env=preflight.expected_worker_environment(paths["runtime"]), stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"full_path_worker_failed:{result.returncode}")
        receipt = json.loads(paths["receipt"].read_text())
        validate_worker_receipt(receipt, manifest, source_sha)
        for name, identity in receipt["frames"].items():
            if runner._file_identity(root / f"{name}.csv") != identity:
                raise RuntimeError("full_path_output_changed")
        frames = {name: batch.read_frame(root / f"{name}.csv") for name in FRAME_NAMES}
        a = equivalence.expected_frames("A0", manifest["formal_identity"])
        batch.validate_daily_calendar(a["daily"], frames["daily"], spec["analysis_end"])
        validator = load("path_validation", "stage009_path_validation.py")
        network = preflight.NetworkBlock()
        check_guard = inference_guard(preflight, registry, spec, (root,))
        with network, check_guard:
            audit = validator.validate_decisions(frames["entry_candidates"], frames["model_decisions"],
                                                 manifest["formal_identity"], check_guard.predict_event)
        if any(check_guard.counters.values()) or network.attempts:
            raise RuntimeError("prediction_audit_safety_failed")
        if (audit["skip_count"] != receipt["audit"]["skip_count"]
                or audit["decision_count"] != receipt["xgboost_inference"]["decision_count"]):
            raise RuntimeError("decision_audit_count_mismatch")
        if audit["skip_count"]:
            validator.validate_prefix(a, frames, audit["first_skip_date"], audit["first_skip_candidate_index"])
        else:
            equivalence.require_frame_equivalence(a, {name: frames[name] for name in base.FRAME_NAMES})
        a_metrics = base.equity_metrics(a["daily"], a["trades"])
        c_metrics = base.equity_metrics(frames["daily"], frames["trades"])
        if c_metrics != receipt["metrics"]:
            raise RuntimeError("full_path_metrics_mismatch")
        archiver = batch.load("path_archive", batch.V4 / "tools/stage006_prefix_equivalence.py")
        archives = {name: archiver.archive_csv(root / f"{name}.csv", identity) for name, identity in receipt["frames"].items()}
        batch.write_json(root / "archive_receipt.json", archives)
        collector = load("path_archive_verifier", "stage005_label_collection.py")
        for name, identity in archives.items():
            collector.verify_archive(root / f"{name}.csv.gz", identity)
        runner.validate_current_input_manifest(manifest)
        summary = {"stage": STAGE, "status": "passed", "A_metrics": a_metrics, "C_metrics": c_metrics,
                   "comparison": validator.primary_comparison(a_metrics, c_metrics), "decision_audit": audit,
                   "prediction_recalculation": check_guard.xgboost_receipt(), "formal_replay_call_count": 1,
                   "historical_model_fit_count": 0, "reviewer_started": False,
                   "receipt_sha256": batch.digest(paths["receipt"]), "file_contract_sha256": manifest["file_contract_sha256"]}
        batch.write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / "failure.json").exists():
            batch.write_json(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        raise
    finally:
        if paths and paths["runtime"].exists():
            shutil.rmtree(paths["runtime"])
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.freeze:
        freeze_inputs()
    elif args.worker:
        run_worker(args)
    else:
        run_parent()


if __name__ == "__main__":
    main()
