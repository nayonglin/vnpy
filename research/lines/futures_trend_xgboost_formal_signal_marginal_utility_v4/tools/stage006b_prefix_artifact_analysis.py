import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stage006b_source", ROOT / "tools/stage006_prefix_equivalence.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
OUTPUT = ROOT / "artifacts/stage006b_prefix_artifact_analysis"


def verify_receipt(receipt, manifest, arm):
    if (manifest["stage"] != "stage006_prefix_equivalence"
            or receipt["stage"] != "stage004_counterfactual_validation"
            or receipt["status"] != "passed" or receipt["arm"] != arm
            or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
            or receipt["formal_identity"] != manifest["formal_identity"]
            or receipt["formal_replay_call_count"] != 1
            or receipt["network_connection_attempt_count"] != 0
            or any(receipt["sensitive_counters"].values())
            or receipt["audit"]["skip_count"] != int(arm == "S")
            or receipt["audit"]["verified_snapshot_count"] != int(arm == "S")):
        raise RuntimeError("component_receipt_invalid")


def main():
    if OUTPUT.exists():
        raise RuntimeError("analysis_already_exists")
    base, runner = source.configured()
    manifest = json.loads((source.OUTPUT / "input_manifest.json").read_text())
    runner.validate_current_input_manifest(manifest)
    failure = json.loads((source.OUTPUT / "failure.json").read_text())
    if failure["error"] != "prefix_worker_receipt_invalid":
        raise RuntimeError("unexpected_prefix_failure")
    columns = {"daily": "date", "trades": "datetime", "positions": "date", "entry_candidates": "datetime",
               "entry_risk": "datetime", "stop_retry_events": "datetime", "root_features": "decision_datetime"}
    results = {}
    receipts = {}
    for arm in ("A", "S"):
        root = source.OUTPUT / "workers" / arm
        if (root / "runtime").exists():
            raise RuntimeError("worker_still_has_runtime")
        receipt = json.loads((root / "receipt.json").read_text())
        verify_receipt(receipt, manifest, arm)
        observed, reference = base.read_frames(root), base.read_frames(source.REFERENCE / "workers" / arm)
        for name, column in columns.items():
            if runner._file_identity(root / f"{name}.csv") != receipt["frames"][name]:
                raise RuntimeError("prefix_frame_changed")
            source.compare_prefix(reference[name], observed[name], column, source.END)
        if observed["daily"].date.max() != source.END:
            raise RuntimeError("wrong_execution_end")
        if base.equity_metrics(observed["daily"], observed["trades"]) != receipt["metrics"]:
            raise RuntimeError("prefix_metrics_mismatch")
        results[arm], receipts[arm] = observed["daily"], receipt
    if receipts["A"]["pid"] == receipts["S"]["pid"]:
        raise RuntimeError("workers_not_distinct")
    target = base.earliest_target()
    marginal = base.account_marginal(results["A"], results["S"], target["decision_date"], source.END,
                                     receipts["S"]["audit"]["pre_event_equity"])
    expected = json.loads((ROOT / "artifacts/stage004b_frozen_artifact_analysis/summary.json").read_text())["marginal"]
    if marginal != expected:
        raise RuntimeError("prefix_label_mismatch")
    archives = {}
    for arm, receipt in receipts.items():
        root = source.OUTPUT / "workers" / arm
        archives[arm] = {name: source.archive_csv(root / f"{name}.csv", identity) for name, identity in receipt["frames"].items()}
        runner._write_json_exclusive(root / "archive_receipt.json", archives[arm])
    runner.validate_current_input_manifest(manifest)
    summary = {
        "stage": "stage006b_prefix_artifact_analysis", "status": "passed", "execution_stage": source.STAGE,
        "component_stage": base.STAGE, "execution_end": source.END, "source_file_contract_sha256": manifest["file_contract_sha256"],
        "source_failure_preserved": True, "prefix_tables_equal": 14, "marginal_equal": True, "marginal": marginal,
        "metrics": {arm: receipt["metrics"] for arm, receipt in receipts.items()}, "archives": archives,
        "analysis_sources": {str(p): source.file_identity(p) for p in (Path(__file__).resolve(),
            ROOT / "tests/test_stage006b_prefix_artifact_analysis.py",
            source.OUTPUT / "failure.json", source.OUTPUT / "input_manifest.json",
            source.OUTPUT / "workers/A/receipt.json", source.OUTPUT / "workers/S/receipt.json")},
        "source_replay_count": 2, "additional_replay_count": 0, "additional_label_count": 0,
        "model_fit_count": 0, "reviewer_started": False,
    }
    OUTPUT.mkdir(mode=0o700)
    runner._write_json_exclusive(OUTPUT / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"archives", "analysis_sources"}}), flush=True)


if __name__ == "__main__":
    main()
