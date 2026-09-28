from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
STAGE = "stage032_migration_path"
OUTPUT = ROOT / "artifacts" / STAGE
MODEL_OUTPUT = ROOT / "artifacts/stage031_migration_training"
FEATURE_OUTPUT = ROOT / "artifacts/stage030_migration_features"
FREEZE = ROOT / "stages/stage032_input_freeze.json"
CONTRACT = ROOT / "stages/20260906_0730_stage031_032_migration_candidate_contract.md"


def load(name):
    spec = importlib.util.spec_from_file_location("migration_path_" + name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def migration():
    return load("stage030_migration_features")


def load_context():
    import pandas as pd

    m = migration()
    summary_path = FEATURE_OUTPUT / "summary.json"
    if m.base.identity(summary_path)["sha256"] != "f438d3e22a8d646d0de7610073bfd7d0eceee43edb6a09106ee7782a5298c83a":
        raise RuntimeError("migration_path_source_summary_changed")
    summary = json.loads(summary_path.read_text())
    path = FEATURE_OUTPUT / "contract_context.csv.gz"
    if (summary["status"] != "migration_features_qualified_no_models"
            or m.base.identity(path) != summary["outputs"][path.name]):
        raise RuntimeError("migration_path_context_changed")
    frame = pd.read_csv(path, float_precision="round_trip")
    if set(frame.columns) != set(m.CONTEXT_IDS + m.FEATURES) or len(frame) != summary["context_count"]:
        raise RuntimeError("migration_path_context_inventory_changed")
    return frame.set_index(["decision_date", "contract_vt_symbol"], drop=False, verify_integrity=True)


def enrich_event(event, context):
    m = migration()
    if (set(m.FEATURES) | {"source_date", "window_start"}) & set(event):
        raise RuntimeError("migration_path_event_already_enriched")
    values = m.features_for_decision(context, event["decision_date"], event["contract_vt_symbol"], event["product_vt_symbol"])
    row = context.loc[(event["decision_date"], event["contract_vt_symbol"])]
    return {**event, "source_date": row.source_date, "window_start": row.window_start, **values}


def validate_decisions(candidates, decisions, formal, predictor, context):
    validator = load("stage009_path_validation")
    required = ["source_date", "window_start", *migration().FEATURES]
    if not set(required).issubset(decisions.columns):
        raise RuntimeError("migration_path_decision_fields_missing")

    def checked_predictor(event):
        enriched = enrich_event(event, context)
        row = decisions.loc[decisions.candidate_index.eq(event["candidate_index"])]
        if len(row) != 1 or any(row.iloc[0][key] != enriched[key] for key in required):
            raise RuntimeError("migration_path_rebuilt_feature_mismatch")
        return predictor(enriched)

    return validator.validate_decisions(candidates, decisions, formal, checked_predictor)


def catalog():
    spec = json.loads((FEATURE_OUTPUT / "candidate_model_spec.json").read_text())
    return load("stage031_migration_training").load_catalog(MODEL_OUTPUT, spec)


def pipeline():
    parent = load("stage009_full_path_replay")
    parent.STAGE, parent.OUTPUT, parent.FREEZE = STAGE, OUTPUT, FREEZE
    parent.MODEL_OUTPUT, parent.CONTRACT, parent.catalog = MODEL_OUTPUT, CONTRACT, catalog
    parent.__file__ = str(Path(__file__).resolve())
    original_collect, original_load = parent.collect_inputs, parent.load

    def collect_inputs():
        files = original_collect()
        for path in (Path(__file__).resolve(), ROOT / "tests/test_stage032_migration_path.py",
                     ROOT / "tools/stage031_migration_training.py", ROOT / "tests/test_stage031_migration_training.py",
                     ROOT / "tools/stage030_migration_features.py", FEATURE_OUTPUT / "contract_context.csv.gz",
                     FEATURE_OUTPUT / "candidate_model_spec.json", FEATURE_OUTPUT / "summary.json"):
            files["migration_path_" + path.name] = path
        return dict(sorted(files.items()))

    def routed_load(name, filename):
        module = original_load(name, filename)
        if filename == "stage009_path_validation.py":
            module.validate_decisions = lambda candidates, decisions, formal, predictor: validate_decisions(
                candidates, decisions, formal, predictor, load_context())
        return module

    parent.collect_inputs, parent.load = collect_inputs, routed_load
    return parent


def run_worker(args):
    batch = load("stage004_label_batch")
    _, runner = batch.configured()
    support = runner.load_metadata_preflight_module()
    preflight = support.load_preflight_module()
    root = args.worker_root.resolve(strict=True)
    runtime = root / "runtime"
    preflight._validate_worker_bootstrap(runtime)
    preflight.prove_external_write_denied(root.parent.parent / "probe_C")
    sys.path.extend([str(preflight.python_site_packages()), str(WORKSPACE)])
    parent = pipeline()
    batch, base, runner = parent.configured()
    manifest = json.loads(args.manifest.read_text())
    runner.validate_current_input_manifest(manifest)
    if runner._file_identity(runtime / ".vntrader/database.db")["sha256"] != manifest["files"]["source_database"]["sha256"]:
        raise RuntimeError("database_copy_mismatch")
    registry, spec, _ = catalog()
    migration_context = load_context()
    attestation = preflight._load_release_attestation(runner.RELEASE_ATTESTATION)
    v1 = runner.load_v1_runner()
    formal = v1._active_formal_identity()
    if formal != manifest["formal_identity"]:
        raise RuntimeError("migration_path_formal_identity_mismatch")
    expected = support.validate_frozen_metadata_files(manifest)
    history = batch.load_history()
    gate = load("stage007_runtime_gate")
    network = preflight.NetworkBlock()
    guard = parent.inference_guard(preflight, registry, spec, (root,), 1)
    guard.assert_no_sensitive_modules_loaded()
    runner._write_json_exclusive(root / "started.json", {"pid": os.getpid(), "arm": "C", "status": "replaying"})
    with network, guard:
        context, adapter_calls, restored = preflight.import_production_context_with_attestation(attestation)
        candidate = sys.modules[runner.CANDIDATE_MODULE_NAME]
        strategy = context["s901"].s847.QmtRollPortfolioStrategyStage847C9StopRetry

        def feature_builder(snapshot):
            current = history.build_features(v1.pd.DataFrame([snapshot]), formal).iloc[0].to_dict()
            return enrich_event(current, migration_context)

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
            raise RuntimeError("migration_path_engine_spec_mismatch")
        features = batch.feature_adapter(raw["entry_candidates"], None, formal)
        decisions = v1.pd.DataFrame(records, columns=[*history.ID_COLUMNS, "source_date", "window_start", *spec["features"],
            "cutoff", "status", "skip", "return_marginal", "drawdown_marginal"])
        frames = {"daily": daily, "root_features": features, "model_decisions": decisions,
                  **{name: raw[name] for name in base.FRAME_NAMES if name not in {"daily", "root_features"}}}
    if (any(guard.counters.values()) or network.attempts or guard.formal_replay_call_count != 1
            or len(adapter_calls) != 1 or not restored or guard.load_count != 1):
        raise RuntimeError("migration_path_worker_safety_failed")
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


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.worker:
        run_worker(args)
    elif args.freeze:
        pipeline().freeze_inputs()
    else:
        pipeline().run_parent()


if __name__ == "__main__":
    main()
