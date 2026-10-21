"""本地保存固定同行对齐AI实验；不训练、不回测、不发布、不重写旧登记。"""
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
OUT = LINE / "outputs/stage036_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage036/20261018_peer_alignment_v1"
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
    inventory_path = LINE / "outputs/stage035_peer_alignment_experiment/artifact_inventory.json"
    inventory = load(inventory_path)
    assert (inventory["starts"], inventory["completed_experiments"], inventory["actual_model_fit_calls"], inventory["financial_runs"]) == (1, 1, 108, 0)
    manifest_path = LINE / "outputs/stage035_peer_alignment_experiment/experiment/manifest.json"
    source_check(manifest_path, {"sha256": "073526fb3439f42b744519b6a7cb7c4a2931d8169e36c040513d27bc44962c51"})
    experiment_manifest = load(manifest_path)
    terminal_path = LINE / "outputs/stage035_peer_alignment_experiment/experiment/actual_terminal.json"
    source_check(terminal_path, {"sha256": "30d7d00de27e1f5b9d1aa07a793802f20e9e4e4f62e1411b608ab1c3990edb36"})
    terminal = load(terminal_path)
    assert (terminal["actual_ridge_fit_calls"], terminal["actual_financial_runs"], terminal["sql_queries"], terminal["exit_code"]) == (108, 0, 0, 0)
    assert terminal["status"] == "completed" and terminal["fixture"] is False
    receipt_path = LINE / "outputs/stage037_peer_alignment_review/review_receipt.json"
    source_check(receipt_path, {"sha256": "aa3aa439ebf37abb69a117493128dd8133e5773e72ed320cef5822c43c155770"})
    receipt = load(receipt_path)
    assert (receipt["critical"], receipt["important"], receipt["minor"]) == (0, 0, 0)
    assert len(receipt["gates"]) == 20 and sum(receipt["gates"].values()) == 3
    assert receipt["quality_information_screen_pass"] is False and receipt["financial_ready"] is False
    assert (receipt["fit_records_checked"], receipt["scalar_predictions_checked"]) == (108, 969654)
    assert receipt["manifest"]["sha256"] == digest(manifest_path)
    context_manifest_path = LINE / "outputs/stage034_peer_alignment_dataset/export/manifest.json"
    context_binding = source_check(context_manifest_path, {"sha256": "2a3abe55eabf0fba5bb5d749fb4343d1bf341e3d217b93619554ab11bf98d990"})
    assert experiment_manifest["input_bindings"]["context_manifest"]["sha256"] == context_binding["sha256"]
    context_review = load(LINE / "outputs/stage037_peer_alignment_review/context_review.json")
    assert context_review["source_manifest"]["sha256"] == context_binding["sha256"]
    assert (context_review["all_ready_rows"], context_review["bounded_scope_cells"]) == (194709, 492)
    inventory037 = load(LINE / "outputs/stage037_peer_alignment_review/artifact_inventory.json")
    assert inventory037["full_q_independent_recomputed"] is False
    return {
        "source035_actual": {"starts": inventory["starts"], "completed_experiments": inventory["completed_experiments"],
                             "actual_model_fit_calls": terminal["actual_ridge_fit_calls"], "financial_runs": terminal["actual_financial_runs"],
                             "sql_queries": terminal["sql_queries"], "exit_code": terminal["exit_code"],
                             "terminal_binding": source_check(terminal_path), "manifest_binding": source_check(manifest_path)},
        "source037_binding": source_check(receipt_path),
        "source037_findings": {"critical": receipt["critical"], "important": receipt["important"], "minor": receipt["minor"],
                               "gates_true": sum(receipt["gates"].values()), "gates_false": len(receipt["gates"])-sum(receipt["gates"].values()),
                               "quality_information_screen_pass": receipt["quality_information_screen_pass"], "financial_ready": receipt["financial_ready"]},
        "context_closure": {"context_manifest": context_binding, "experiment_and_context_review_bind_same_context": True,
                            "context_ready_rows": context_review["all_ready_rows"], "bounded_scope_cells": context_review["bounded_scope_cells"],
                            "full_q_independent_recomputed": False,
                            "scope_limit": "保留原独审的492格独立重建边界，不声称独立全量q重算；本登记不重跑研究。"},
    }


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None) -> None:
        row = source_check(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage033_fixed_peer_alignment_information_v1")
        if path in rows:
            assert rows[path] == row, path
        rows[path] = row

    expected_inventories = {
        34: (12, "ee73e9013457a74c217a355729114027242f026056807b9e23ebe50d6fb545df"),
        35: (167, "3c5d0bd44e95de634f86533ed7fc7f376907677f78c84e615bdf70d430ec4f63"),
        37: (8, "4df4bd3f4889f2c58e88a7be93ef028cc2e3e3ef52db42131059a7818cd31932"),
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
    add(LINE / "outputs/stage033_peer_alignment_protocol/protocol.json", "feature_contract",
        {"sha256": "6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b"})
    add(unique_stage(33), "feature_contract", {"sha256": "7370e8fc05bbbc9e8a0436f2e63abc4078ba8ad43e8d33c46837e58d79e281be"})
    add(unique_stage(36), "decision_asset", {"sha256": "b085afe9d16ffbaa9c91636bf5fd2d323d46651cc9c773d3ac19c6e5ba1cbe00"})
    add(unique_stage(38), "decision_asset", {"sha256": "769fddd904963fc7befc860fe5934221f6a361b041b2734e6bcd8a6618cf7edf"})
    add(LINE / "outputs/stage038_cross_session_policy_mother_design/read_receipt.json", "qualification_evidence",
        {"sha256": "8675c64fad161ab5773bae7bd39efba8a8466a965bbb9c2e58520e9d74988991"})
    add(Path(__file__).absolute(), "qualification_evidence")
    names = [x["logical_name"] for x in rows.values()]
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
    role_rows = sorted(rows.values(), key=lambda row: row["logical_name"])
    dump(OUT / "role_mapping.json", {"schema": "stage036_explicit_role_mapping_v1", "artifacts": role_rows,
        "role_counts": dict(Counter(row["role"] for row in role_rows)),
        "mapping_scope": "源清单逐项显式角色，新增协议/决策/收据按功能声明；不靠文件名推断重要性。自身与请求的角色由最终manifest显式记录。"})
    dump(OUT / "finite_closure.json", {"schema": "stage036_finite_registration_closure_v1", "status": "passed", **checks,
        "declared_inventory_counts": {str(n): count for n, (count, _) in expected_inventories.items()},
        "selected_source_assets_sha_size_verified": len(rows), "raw_sources_rehashed": False,
        "closure_scope": "仅本轮清单源/结果/小协议及审查引用闭包；009与023旧大输入、DB、raw价格只保留已有引用，不复制、不重哈希，不代替金融资格。",
        "sql_queries": 0, "model_fits": 0, "financial_runs": 0})
    add(OUT / "role_mapping.json", "qualification_evidence")
    add(OUT / "finite_closure.json", "qualification_evidence")
    index_before = git("ls-files", "--stage")
    dump(OUT / "registration_request.json", {
        "schema": "stage036_exact_local_registration_request_v1", "created_at": stamp(),
        "line_id": LINE.name, "stage": "stage036", "run_id": "20261018_peer_alignment_v1",
        "destination": str(DEST), "source_commit": git("rev-parse", "HEAD").strip(),
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "request_self_included_as_qualification_evidence_without_recursive_self_digest": True, **checks,
        "upstream_archives_reference_only": ["research/ai_assets/futures_full_market_long_signal_ai/stage013/20261018_fixed_day_quality_v1/manifest.json",
                                            "research/ai_assets/futures_full_market_long_signal_ai/stage026/20261018_ordered_history_v1/manifest.json"],
        "explicit_excluded_raw_price_files": sorted(excluded_names), "raw_market_data_copied": False,
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
        "research_judgment": "保存固定同行关系失败筛选及独审结果，无新增alpha选择或救参；新跨期政策设计独立保留，不声称已有金融优势。",
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
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage036_local_registration/registration_request", "qualification_evidence", True))
    fresh_checks()
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage036", run_id="20261018_peer_alignment_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {
        "schema": "stage036_local_registration_receipt_v1", "finished_at": stamp(), "status": "registered_and_exact_staged",
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
        "schema": "stage036_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
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
