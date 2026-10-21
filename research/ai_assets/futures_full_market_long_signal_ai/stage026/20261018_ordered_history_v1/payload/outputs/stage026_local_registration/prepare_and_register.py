"""本地保存固定 ORDER/BAG 实验；不训练、不回测、不发布、不重写旧登记。"""
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
OUT = LINE / "outputs/stage026_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage026/20261018_ordered_history_v1"
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


def unique_stage(number: int) -> Path:
    paths = list((LINE / "stages").glob(f"*stage{number:03d}_*"))
    assert len(paths) == 1, (number, paths)
    return paths[0]


def fresh_checks() -> dict:
    inventory_path = LINE / "outputs/stage024_ordered_history_experiment/artifact_inventory.json"
    inventory = load(inventory_path)
    assert (inventory["starts"], inventory["completed_experiments"], inventory["actual_fit_calls"], inventory["financial_runs"]) == (1, 1, 108, 0)
    terminal_path = LINE / "outputs/stage024_ordered_history_experiment/experiment/actual_terminal.json"
    terminal = load(terminal_path)
    assert (terminal["actual_ridge_fit_calls"], terminal["actual_financial_runs"], terminal["exit_code"]) == (108, 0, 0)
    assert terminal["status"] == "completed" and terminal["fixture"] is False
    receipt_path = LINE / "outputs/stage025_ordered_history_review/review_receipt.json"
    source_check(receipt_path, {"sha256": "4b17b43540a95ee1f9fb7afd42fc64341ebecb61fb1815152643760629796b3b"})
    receipt = load(receipt_path)
    assert (receipt["critical"], receipt["important"], receipt["minor"]) == (0, 0, 0)
    assert len(receipt["gates"]) == 20 and sum(receipt["gates"].values()) == 2
    assert receipt["quality_information_screen_pass"] is False and receipt["financial_ready"] is False
    assert (receipt["fit_records_checked"], receipt["scalar_predictions_checked"]) == (108, 969654)
    return {
        "source024_actual": {"starts": inventory["starts"], "completed_experiments": inventory["completed_experiments"],
                             "actual_fit_calls": terminal["actual_ridge_fit_calls"], "financial_runs": terminal["actual_financial_runs"],
                             "exit_code": terminal["exit_code"], "terminal_binding": source_check(terminal_path)},
        "source025_binding": source_check(receipt_path),
        "source025_findings": {"critical": receipt["critical"], "important": receipt["important"], "minor": receipt["minor"],
                               "gates_true": sum(receipt["gates"].values()), "gates_false": len(receipt["gates"])-sum(receipt["gates"].values()),
                               "quality_information_screen_pass": receipt["quality_information_screen_pass"],
                               "financial_ready": receipt["financial_ready"]},
    }


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    # Root supplies final Stage027 paths/digests after that independent author has frozen them.
    stage027 = load(OUT / "stage027_final_bindings.json")
    assert stage027["frozen"] is True and stage027["root_authorized_final_assets"] is True
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None) -> None:
        row = source_check(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage022_fixed_ordered_history_information_v1")
        if path in rows:
            assert rows[path] == row, path
        rows[path] = row

    expected_inventories = {
        23: (12, "2e471c2e0bdcdc90ff9c1df0ccd83edeebe774f1d0d49e6363368b1866fc85e5"),
        24: (169, "906dff0beba18efa6c1ee6b3af2ad6b123b0545a5e8d9c89070843dc01e3f34c"),
        25: (8, "3b3c56454b1e5222d22e7a5f534736a6cfc8ccdda04db8e8ff728d53f61f498f"),
    }
    for number, (count, sha) in expected_inventories.items():
        inventories = list((LINE / "outputs").glob(f"stage{number:03d}*/artifact_inventory.json"))
        assert len(inventories) == 1
        path = inventories[0]
        source_check(path, {"sha256": sha})
        declared_inventory = load(path)
        assert len(declared_inventory["artifacts"]) == count
        for declared in declared_inventory["artifacts"]:
            assert declared.get("raw_ohlc", False) is False
            if declared["reproducibility_required"]:
                add(Path(declared["path"]), declared["role"], declared)
        add(path, "qualification_evidence")
    add(LINE / "outputs/stage022_ordered_history_protocol/protocol.json", "feature_contract",
        {"sha256": "ae0708cb9eb232d5c5d7936fc705f77b2f361e4b039442e707b82c828b27f99a"})
    add(unique_stage(22), "feature_contract", {"sha256": "3d35c65109db530e4d37818e91ee0e52e3a15f68001fcc5549d3b3cc83c2e967"})
    add(unique_stage(26), "decision_asset", {"sha256": "1f4f757e4e01d59cbd25486248c8fa1219f1edbb7269e3ead87bed8008e6ea87"})
    for declared in stage027["artifacts"]:
        assert declared["reproducibility_required"] is True
        add(Path(declared["path"]), declared["role"], declared)
    add(OUT / "stage027_final_bindings.json", "qualification_evidence")
    add(Path(__file__).absolute(), "qualification_evidence")
    names = [x["logical_name"] for x in rows.values()]
    # Different formats can share a stem (representation_review.py/json). Keep
    # the original basename and segregate just those collisions by format.
    duplicate_names = {name for name, count in Counter(names).items() if count > 1}
    for path, row in rows.items():
        if row["logical_name"] in duplicate_names:
            relative = path.relative_to(LINE)
            row["logical_name"] = str(relative.parent / ("format_" + path.suffix.lstrip(".")) / relative.with_suffix("").name)
    names = [x["logical_name"] for x in rows.values()]
    assert len(names) == len(set(names))
    excluded_names = {"clean_daily.sqlite", "audit_paths.csv.gz", "feature_labels.csv.gz", "product_day_opportunities.csv.gz"}
    assert not any(path.name in excluded_names or path.suffix in {".env", ".sqlite", ".db", ".npy"} for path in rows)
    assert not any("stage020/20261018_entry_confirmation_v1" in str(path) for path in rows)
    checks = fresh_checks()
    index_before = git("ls-files", "--stage")
    dump(OUT / "registration_request.json", {
        "schema": "stage026_exact_local_registration_request_v1", "created_at": stamp(),
        "line_id": LINE.name, "stage": "stage026", "run_id": "20261018_ordered_history_v1",
        "destination": str(DEST), "source_commit": git("rev-parse", "HEAD").strip(),
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "request_self_included_as_qualification_evidence_without_recursive_self_digest": True,
        **checks,
        "upstream_archives_reference_only": ["research/ai_assets/futures_full_market_long_signal_ai/stage013/20261018_fixed_day_quality_v1/manifest.json",
                                            "research/ai_assets/futures_full_market_long_signal_ai/stage020/20261018_entry_confirmation_v1/manifest.json"],
        "explicit_excluded_raw_price_files": sorted(excluded_names), "raw_market_data_copied": False,
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
        "research_judgment": "保存失败信息筛选及独审结果，不新增或救参；继续价值须来自不同问题而非重复已失败字段。",
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
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage026_local_registration/registration_request", "qualification_evidence", True))
    fresh_checks()
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage026", run_id="20261018_ordered_history_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {
        "schema": "stage026_local_registration_receipt_v1", "finished_at": stamp(), "status": "registered_and_exact_staged",
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
    result = {
        "schema": "stage026_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
        "manifest_path": str(manifest_path), "manifest_file_sha256": digest(manifest_path), "manifest_canonical_sha256": expected_digest,
        "payload_count": len(checks), "payload_bytes": sum(row["bytes"] for row in checks), "staged_count": len(staged),
        "role_counts": dict(Counter(row["role"] for row in manifest["artifacts"])), "source_and_copy_sha_size_all_match": True,
        "exact_staged_prefix_matches": True, "unrelated_index_entries_preserved": True, "checks": checks,
        **fresh_checks(),
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
    }
    dump(OUT / "final_verification.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "register", "verify"])
    args = parser.parse_args()
    {"prepare": prepare, "register": register, "verify": verify}[args.mode]()
