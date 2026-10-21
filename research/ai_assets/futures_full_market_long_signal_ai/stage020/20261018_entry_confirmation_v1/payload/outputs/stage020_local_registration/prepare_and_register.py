"""精确登记 Stage015--021 的本地复现资产；不训练、不回测、不发布。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).absolute().parents[5]
LINE = ROOT / "research/lines/futures_full_market_long_signal_ai"
OUT = LINE / "outputs/stage020_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage020/20261018_entry_confirmation_v1"
sys.path.insert(0, str(ROOT / "examples/portfolio_backtesting"))
from qmt_roll_ai_artifact_registry import AiArtifact, register_experiment_artifacts
from qmt_roll_strategy_material_manifest import canonical_json_bytes


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def load(path: Path) -> object:
    return json.loads(path.read_text())


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def source_check(path: Path, expected: dict | None = None) -> dict:
    assert path.is_file() and not path.is_symlink(), path
    assert path.is_relative_to(LINE), path
    actual = {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size}
    if expected:
        assert actual["sha256"] == expected["sha256"], (path, "sha256")
        if "bytes" in expected:
            assert actual["size_bytes"] == expected["bytes"], (path, "bytes")
    return actual


def stage(number: int) -> Path:
    paths = list((LINE / "stages").glob(f"*stage{number:03d}_*"))
    assert len(paths) == 1, (number, paths)
    return paths[0]


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None) -> None:
        row = source_check(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage015_all_ready_entry_confirmation_v1")
        if path in rows:
            assert rows[path] == row, path
        rows[path] = row

    inventory_path = LINE / "outputs/stage018_entry_confirmation_experiment/artifact_inventory.json"
    source_check(inventory_path, {"sha256": "1dfa376f5e4192cb510891c67098feaa1ed429a4a00a38887fa845990c23f894"})
    inventory = load(inventory_path)
    assert (inventory["attempts"], inventory["completed_full_experiment"], inventory["model_fits"], inventory["financial_runs"]) == (3, 1, 0, 0)
    assert len(inventory["artifacts"]) == 61
    for declared in inventory["artifacts"]:
        if declared["reproducibility_required"]:
            add(Path(declared["path"]), declared["role"], declared)
    add(inventory_path, "qualification_evidence")

    add(LINE / "outputs/stage015_entry_confirmation_protocol/protocol.json", "feature_contract",
        {"sha256": "73c991c2ed2c4d4dbc77147705b6f09d834e63c05d7a8b0f614a902c1b6ec5e9"})
    add(stage(15), "feature_contract")
    stage016 = LINE / "outputs/stage016_existing_intraday_coverage"
    for name in ["input_inventory.json", "handoff_manifest.json", "actual_terminal.json", "inventory.py",
                 "current_workspace_candidate_files.csv", "product_scope_inventory.csv",
                 "inherited_accepted_session_product_year.csv", "initial_missing_source.json"]:
        add(stage016 / name, "feature_contract" if name == "inventory.py" else "qualification_evidence")
    add(stage(16), "qualification_evidence")
    stage017 = LINE / "outputs/stage017_entry_path_bounds_design"
    for name in ["synthetic_oracle.py", "synthetic_results.json", "actual_terminal.json"]:
        add(stage017 / name, "qualification_evidence")
    add(stage(17), "qualification_evidence")

    handoff_path = LINE / "outputs/stage019_entry_confirmation_review/handoff_manifest.json"
    for path, declared in load(handoff_path)["artifacts"].items():
        add(Path(path), "qualification_evidence", declared)
    add(handoff_path, "qualification_evidence")
    add(stage(20), "decision_asset")
    add(stage(21), "feature_contract", {"sha256": "f64dfcef8c7066dcd6354f195bf0ce1e6b98a685efc011837d1056bbdf77d4ca"})
    add(LINE / "outputs/stage021_ordered_history_information_review/read_receipt.json", "qualification_evidence",
        {"sha256": "292a7b665e3186bf860f35f94fc577544bf500bf8e96127ab9863c1a52150b77"})
    add(Path(__file__).absolute(), "qualification_evidence")
    terminal_path = LINE / "outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/actual_terminal.json"
    terminal = load(terminal_path)
    assert (terminal["attempts"], terminal["completed_full_experiment"], terminal["model_fits"], terminal["financial_runs"], terminal["exit_code"]) == (3, 1, 0, 0, 0)
    review_path = LINE / "outputs/stage019_entry_confirmation_review/review_receipt.json"
    source_check(review_path, {"sha256": "1667fc9985c072a853b0dbca1a1c59efacabcfc7ad3fa468d0b50da79ba02625"})
    review = load(review_path)
    assert (review["Critical"], review["Important"], review["Minor"], review["gates_true"], review["gates_false"]) == (0, 0, 0, 2, 13)
    assert review["quality_screen_pass"] is False and review["financial_ready"] is False
    names = [x["logical_name"] for x in rows.values()]
    assert len(names) == len(set(names))
    excluded_names = {"bounded_csv_endpoints.json", "database_metadata_and_probes.json", "clean_daily.sqlite", "audit_paths.csv.gz", "feature_labels.csv.gz", "product_day_opportunities.csv.gz"}
    assert not any(path.name in excluded_names or path.suffix in {".env", ".sqlite", ".db", ".npy"} for path in rows)
    index_before = git("ls-files", "--stage")
    dump(OUT / "registration_request.json", {
        "schema": "stage020_exact_local_registration_request_v1", "created_at": stamp(),
        "line_id": LINE.name, "stage": "stage020", "run_id": "20261018_entry_confirmation_v1",
        "destination": str(DEST), "source_commit": git("rev-parse", "HEAD").strip(),
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "request_self_included_as_qualification_evidence_without_recursive_self_digest": True,
        "source018_counts": {k: terminal[k] for k in ["attempts", "completed_full_experiment", "model_fits", "financial_runs", "exit_code"]},
        "source019_binding": source_check(review_path),
        "source019_findings": {k: review[k] for k in ["Critical", "Important", "Minor", "gates_true", "gates_false", "quality_screen_pass"]},
        "explicit_excluded_raw_price_files": sorted(excluded_names), "raw_market_data_copied": False,
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
        "research_judgment": "仅保存既有结果，无新增alpha选择；候选筛选失败保留。继续研究价值在于新信息问题，不救本入场参数。",
    })
    (OUT / "index_before.txt").write_text(index_before)
    print(json.dumps({"status": "prepared", "payload_count_with_request": len(rows) + 1,
                      "bytes_excluding_request": sum(row["size_bytes"] for row in rows.values()),
                      "request_sha256": digest(OUT / "registration_request.json")}, ensure_ascii=False))


def register() -> None:
    request = load(OUT / "registration_request.json")
    artifacts = []
    for row in request["artifacts"]:
        path = Path(row["path"])
        source_check(path, {"sha256": row["sha256"], "bytes": row["size_bytes"]})
        artifacts.append(AiArtifact(path, row["logical_name"], row["role"], True, row["feature_schema_version"]))
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage020_local_registration/registration_request", "qualification_evidence", True))
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage020", run_id="20261018_entry_confirmation_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {
        "schema": "stage020_local_registration_receipt_v1", "finished_at": stamp(), "status": "registered_and_exact_staged",
        "destination": str(result.destination), "manifest_path": str(result.manifest_path),
        "manifest_file_sha256": digest(result.manifest_path), "copied_count": len(result.copied_logical_names),
        "staged_count": len(result.staged_paths), "staged_paths": result.staged_paths,
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
    })
    print(json.dumps({"status": "registered_and_exact_staged", "copied_count": len(result.copied_logical_names),
                      "staged_count": len(result.staged_paths), "manifest_file_sha256": digest(result.manifest_path)}, ensure_ascii=False))


def verify() -> None:
    manifest_path = DEST / "manifest.json"
    manifest = load(manifest_path)
    expected_digest = manifest.pop("manifest_sha256")
    assert hashlib.sha256(canonical_json_bytes(manifest)).hexdigest() == expected_digest
    checks = []
    allowed_roles = {"decision_asset", "model_artifact", "feature_contract", "qualification_evidence"}
    expected = {manifest_path.relative_to(ROOT).as_posix()}
    for row in manifest["artifacts"]:
        source = Path(row["source_path"])
        target = DEST / row["path"]
        assert row["role"] in allowed_roles and row["reproducibility_required"] is True
        assert source.is_file() and target.is_file() and not source.is_symlink() and not target.is_symlink()
        assert source.stat().st_size == target.stat().st_size == row["size_bytes"]
        assert digest(source) == digest(target) == row["sha256"]
        expected.add(target.relative_to(ROOT).as_posix())
        checks.append({"logical_name": row["logical_name"], "sha256": row["sha256"], "bytes": row["size_bytes"], "source_copy_match": True})
    prefix = DEST.relative_to(ROOT).as_posix()
    staged = set(git("diff", "--cached", "--name-only", "--", prefix).splitlines())
    assert staged == expected, {"missing": sorted(expected-staged), "extra": sorted(staged-expected)}
    before = (OUT / "index_before.txt").read_text().splitlines()
    after = git("ls-files", "--stage").splitlines()
    before_outside = {line for line in before if not line.split("\t", 1)[1].startswith(prefix + "/")}
    after_outside = {line for line in after if not line.split("\t", 1)[1].startswith(prefix + "/")}
    assert before_outside == after_outside, "unrelated index entries changed"
    source018 = LINE / "outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/actual_terminal.json"
    terminal = load(source018)
    assert (terminal["attempts"], terminal["completed_full_experiment"], terminal["model_fits"], terminal["financial_runs"], terminal["exit_code"]) == (3, 1, 0, 0, 0)
    source019 = LINE / "outputs/stage019_entry_confirmation_review/review_receipt.json"
    assert digest(source019) == "1667fc9985c072a853b0dbca1a1c59efacabcfc7ad3fa468d0b50da79ba02625"
    review = load(source019)
    assert (review["Critical"], review["Important"], review["Minor"], review["gates_true"], review["gates_false"]) == (0, 0, 0, 2, 13)
    result = {
        "schema": "stage020_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
        "manifest_path": str(manifest_path), "manifest_file_sha256": digest(manifest_path), "manifest_canonical_sha256": expected_digest,
        "payload_count": len(checks), "payload_bytes": sum(row["bytes"] for row in checks), "staged_count": len(staged),
        "role_counts": dict(Counter(row["role"] for row in manifest["artifacts"])), "source_and_copy_sha_size_all_match": True,
        "exact_staged_prefix_matches": True, "unrelated_index_entries_preserved": True, "checks": checks,
        "source018_fresh_counts": {key: terminal[key] for key in ["attempts", "completed_full_experiment", "model_fits", "financial_runs", "exit_code"]},
        "source019_fresh_binding": source_check(source019),
        "source019_fresh_findings": {key: review[key] for key in ["Critical", "Important", "Minor", "gates_true", "gates_false", "quality_screen_pass"]},
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
    }
    dump(OUT / "final_verification.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "register", "verify"])
    args = parser.parse_args()
    {"prepare": prepare, "register": register, "verify": verify}[args.mode]()
