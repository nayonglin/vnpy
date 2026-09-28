import importlib.util
import json
from pathlib import Path

import pandas as pd
from vnpy.trader.constant import Direction, Offset


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/stage004_counterfactual_validation"
OUTPUT = ROOT / "artifacts/stage004b_frozen_artifact_analysis"
spec = importlib.util.spec_from_file_location("stage004b_base", ROOT / "tools/stage004_counterfactual_validation.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def load_frames(root):
    frames = base.read_frames(root)
    # Match Stage003's frozen qualification parser; other tables keep round-trip precision.
    frames["root_features"] = pd.read_csv(root / "root_features.csv")
    trades = frames["trades"].copy()
    for column, mapping in {
        "direction": {Direction.LONG.value: "Long", Direction.SHORT.value: "Short",
                      "\u591a": "Long", "\u7a7a": "Short"},
        "offset": {Offset.OPEN.value: "Open", Offset.CLOSE.value: "Close",
                   Offset.CLOSETODAY.value: "CloseToday", Offset.CLOSEYESTERDAY.value: "CloseYesterday",
                   "\u5f00": "Open", "\u5e73": "Close", "\u5e73\u4eca": "CloseToday", "\u5e73\u6628": "CloseYesterday"},
    }.items():
        converted = trades[column].map(mapping)
        if converted.isna().any():
            raise RuntimeError(f"unknown_vnpy_trade_enum:{column}")
        trades[column] = converted
    frames["trades"] = trades
    return frames


def main():
    if OUTPUT.exists():
        raise RuntimeError("analysis_output_already_exists")
    runner = base.support()
    manifest = json.loads((SOURCE / "input_manifest.json").read_text())
    runner.validate_current_input_manifest(manifest)
    failure = json.loads((SOURCE / "failure.json").read_text())
    if failure["error"] != "worker_reproducibility_failed:worker_qualification_mismatch":
        raise RuntimeError("unexpected_source_failure")
    source_files = [SOURCE / "input_manifest.json", SOURCE / "failure.json", SOURCE / "target.json",
                    ROOT / "stages/20260905_stage004_execution_state/claim.json",
                    ROOT / "stages/20260905_stage004_input_contract_freeze.json",
                    Path(__file__).resolve(), ROOT / "tests/test_stage004b_frozen_artifact_analysis.py",
                    ROOT / "stages/20260905_stage004b_readonly_analysis_contract.md"]
    target = json.loads((SOURCE / "target.json").read_text())
    if target != base.earliest_target():
        raise RuntimeError("frozen_target_changed")
    results = []
    for arm in base.ARMS:
        root = SOURCE / "workers" / arm
        if (root / "runtime").exists():
            raise RuntimeError("worker_runtime_not_cleaned")
        receipt_path = root / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        source_files.append(receipt_path)
        if (receipt["status"] != "passed" or receipt["arm"] != arm
                or receipt["stage"] != base.STAGE
                or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
                or receipt["formal_replay_call_count"] != 1
                or receipt["network_connection_attempt_count"] != 0
                or any(receipt["sensitive_counters"].values())):
            raise RuntimeError(f"invalid_worker_receipt:{arm}")
        if receipt["audit"]["skip_count"] != int(arm == "S") or receipt["audit"]["verified_snapshot_count"] != int(arm == "S"):
            raise RuntimeError(f"invalid_intervention_count:{arm}")
        for name in base.FRAME_NAMES:
            path = root / f"{name}.csv"
            source_files.append(path)
            if runner._file_identity(path) != receipt["frames"][name]:
                raise RuntimeError(f"worker_frame_drift:{arm}:{name}")
            if arm == "A0" and path.read_bytes() != (SOURCE / "workers/A" / f"{name}.csv").read_bytes():
                raise RuntimeError(f"noop_bytes_differ:{name}")
        frames = load_frames(root)
        if base.equity_metrics(frames["daily"], frames["trades"]) != receipt["metrics"]:
            raise RuntimeError(f"worker_metrics_mismatch:{arm}")
        results.append({"receipt": receipt, "frames": frames})
    if len({item["receipt"]["pid"] for item in results}) != 3:
        raise RuntimeError("workers_not_distinct")
    if (SOURCE / "workers/A/root_features.csv").read_bytes() != (base.UPSTREAM / "event_features.csv").read_bytes():
        raise RuntimeError("upstream_feature_bytes_differ")
    source_files.append(base.UPSTREAM / "event_features.csv")
    source_identities = {str(path.resolve()): runner._file_identity(path) for path in source_files}
    validation = base.validate_results(results, target)
    if not validation["label_mechanism_ready"]:
        raise RuntimeError(f"root_endpoint_not_mature:{validation['endpoint']}")
    runner.validate_current_input_manifest(manifest)
    for path, identity in source_identities.items():
        if runner._file_identity(Path(path)) != identity:
            raise RuntimeError(f"analysis_input_drift:{path}")
    summary = {
        "stage": "stage004b_frozen_artifact_analysis", "status": "passed",
        "source_stage": base.STAGE, "source_stage_status": "analysis_failed",
        "source_file_contract_sha256": manifest["file_contract_sha256"],
        "source_identities": source_identities, "target": target, **validation,
        "noop_bytes_equal": True, "upstream_feature_bytes_equal": True,
        "metrics": {arm: result["receipt"]["metrics"] for arm, result in zip(base.ARMS, results)},
        "source_formal_replay_call_count": 3, "additional_replay_count": 0,
        "label_count": 1, "model_fit_count": 0, "reviewer_started": False,
        "enum_mapping_source": "frozen producer constant.py raw zh_CN plus local Direction/Offset.value",
        "feature_parser": "Stage003 pandas default", "account_parser": "round_trip",
    }
    OUTPUT.mkdir(mode=0o700)
    runner._write_json_exclusive(OUTPUT / "summary.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key != "source_identities"}), flush=True)


if __name__ == "__main__":
    main()
