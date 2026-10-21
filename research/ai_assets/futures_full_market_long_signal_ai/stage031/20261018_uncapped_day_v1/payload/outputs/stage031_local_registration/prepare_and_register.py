"""本地保存固定取消止盈政策实验；不训练、不回测、不发布、不重写旧登记。"""
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
OUT = LINE / "outputs/stage031_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage031/20261018_uncapped_day_v1"
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
    inventory_path = LINE / "outputs/stage029_uncapped_day_experiment/artifact_inventory.json"
    inventory = load(inventory_path)
    assert (inventory["starts"], inventory["completed_experiments"], inventory["model_fits"], inventory["financial_runs"]) == (2, 1, 0, 0)
    manifest_path = LINE / "outputs/stage029_uncapped_day_experiment/experiment_after_status_fix/manifest.json"
    source_check(manifest_path, {"sha256": "3af02dfdf3eda1b61a5a1e325bb21f72bfd2f309edb589ffdc6633497732181a"})
    terminal_path = LINE / "outputs/stage029_uncapped_day_experiment/experiment_after_status_fix/actual_terminal.json"
    source_check(terminal_path, {"sha256": "29f4d6660d20d1026360f97062cbd48a9b9c25dad4d3a83d48f454cd74cc46a5"})
    terminal = load(terminal_path)
    assert (terminal["actual_model_fit_calls"], terminal["financial_runs"], terminal["sql_queries"], terminal["exit_code"]) == (0, 0, 0, 0)
    assert terminal["status"] == "completed" and terminal["fixture"] is False
    receipt_path = LINE / "outputs/stage030_uncapped_day_review/review_receipt.json"
    source_check(receipt_path, {"sha256": "fe6bca3c2d3e90675ad2a7f859b3eed3ad6d55f713647ea130fe542194763ef1"})
    receipt = load(receipt_path)
    assert (receipt["critical"], receipt["important"], receipt["minor"]) == (0, 0, 0)
    assert len(receipt["gates"]) == 11 and sum(receipt["gates"].values()) == 2
    assert receipt["uncapped_policy_screen_pass"] is False and receipt["financial_ready"] is False
    assert (receipt["full_event_rows_checked"], receipt["identified_rows_checked"], receipt["scope_period_reports_checked"]) == (399252, 194168, 76)
    return {
        "source029_actual": {"starts": inventory["starts"], "completed_experiments": inventory["completed_experiments"],
                             "model_fits": terminal["actual_model_fit_calls"], "financial_runs": terminal["financial_runs"],
                             "sql_queries": terminal["sql_queries"], "exit_code": terminal["exit_code"],
                             "terminal_binding": source_check(terminal_path), "manifest_binding": source_check(manifest_path)},
        "source030_binding": source_check(receipt_path),
        "source030_findings": {"critical": receipt["critical"], "important": receipt["important"], "minor": receipt["minor"],
                               "gates_true": sum(receipt["gates"].values()), "gates_false": len(receipt["gates"])-sum(receipt["gates"].values()),
                               "uncapped_policy_screen_pass": receipt["uncapped_policy_screen_pass"], "financial_ready": receipt["financial_ready"]},
    }


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None) -> None:
        row = source_check(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage028_fixed_uncapped_day_policy_v1")
        if path in rows:
            assert rows[path] == row, path
        rows[path] = row

    expected_inventories = {
        29: (27, "a465a30aa0be66ec24c777aeb7f1c0c56dcbf4cb1e871d786cd10d90da67d15b"),
        30: (5, "b9c06432f4d34758bead30c7e39dbbab7448fd570eb4be14e771dfea19a94d9f"),
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
    add(LINE / "outputs/stage028_uncapped_day_protocol/protocol.json", "feature_contract",
        {"sha256": "5c2ed793c64f74d503e7a474a93e4885905087b087e7925756c8395eb35100f2"})
    add(unique_stage(28), "feature_contract", {"sha256": "b9e1e3a2eb5b552b189fe7186abbe43b03e5e5991912c8e22785b6f1fe32d065"})
    add(unique_stage(31), "decision_asset", {"sha256": "2910b48dd8f7ddfb3a35224534c6250727b2ef24de64bb7c0bcfd8e1f51dab0d"})
    add(unique_stage(32), "decision_asset", {"sha256": "d396bb4f5717c1104f85469fb675ac3f3cfe8e20a5db51cf8865e17de5c21c9b"})
    add(LINE / "outputs/stage032_cross_family_aligned_state_design/read_receipt.json", "qualification_evidence",
        {"sha256": "2110729e57868135e0b4eb4a9e99ad71fa8aa8cfbb86745b73f9151383f5ebdf"})
    add(Path(__file__).absolute(), "qualification_evidence")
    names = [x["logical_name"] for x in rows.values()]
    # Preserve both formats if source basenames share their stem.
    duplicate_names = {name for name, count in Counter(names).items() if count > 1}
    for path, row in rows.items():
        if row["logical_name"] in duplicate_names:
            relative = path.relative_to(LINE)
            row["logical_name"] = str(relative.parent / ("format_" + path.suffix.lstrip(".")) / relative.with_suffix("").name)
    names = [x["logical_name"] for x in rows.values()]
    assert len(names) == len(set(names))
    excluded_names = {"clean_daily.sqlite", "audit_paths.csv.gz", "feature_labels.csv.gz", "product_day_opportunities.csv.gz", "ordered_history.npz"}
    assert not any(path.name in excluded_names or path.suffix in {".env", ".sqlite", ".db", ".npy"} for path in rows)
    assert not any("research/ai_assets" in str(path) for path in rows)
    checks = fresh_checks()
    index_before = git("ls-files", "--stage")
    dump(OUT / "registration_request.json", {
        "schema": "stage031_exact_local_registration_request_v1", "created_at": stamp(),
        "line_id": LINE.name, "stage": "stage031", "run_id": "20261018_uncapped_day_v1",
        "destination": str(DEST), "source_commit": git("rev-parse", "HEAD").strip(),
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "request_self_included_as_qualification_evidence_without_recursive_self_digest": True,
        **checks,
        "upstream_archives_reference_only": ["research/ai_assets/futures_full_market_long_signal_ai/stage013/20261018_fixed_day_quality_v1/manifest.json",
                                            "research/ai_assets/futures_full_market_long_signal_ai/stage020/20261018_entry_confirmation_v1/manifest.json",
                                            "research/ai_assets/futures_full_market_long_signal_ai/stage026/20261018_ordered_history_v1/manifest.json"],
        "explicit_excluded_raw_price_files": sorted(excluded_names), "raw_market_data_copied": False,
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
        "research_judgment": "保存失败政策筛选及独审结果，无新增alpha选择或救参；继续价值来自新的跨族状态信息问题。",
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
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage031_local_registration/registration_request", "qualification_evidence", True))
    fresh_checks()
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage031", run_id="20261018_uncapped_day_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {
        "schema": "stage031_local_registration_receipt_v1", "finished_at": stamp(), "status": "registered_and_exact_staged",
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
        "schema": "stage031_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
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
