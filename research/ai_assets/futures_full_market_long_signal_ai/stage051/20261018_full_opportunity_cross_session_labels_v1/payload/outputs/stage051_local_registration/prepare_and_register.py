"""Stage051 最终交付后才允许登记；准备期间绝不复制半成品或暂存 Git。"""
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
OUT = LINE / "outputs/stage051_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage051/20261018_full_opportunity_cross_session_labels_v1"
sys.path.insert(0, str(ROOT / "examples/portfolio_backtesting"))
from qmt_roll_ai_artifact_registry import AiArtifact, register_experiment_artifacts
from qmt_roll_strategy_material_manifest import canonical_json_bytes

ALLOWED_ROLES = {"decision_asset", "model_artifact", "feature_contract", "qualification_evidence"}
REGISTRY_ROLE_MAP = {
    "decision_asset": "decision_asset",
    "model_artifact": "model_artifact",
    "feature_contract": "feature_contract",
    "qualification_evidence": "qualification_evidence",
    "feature_matrix": "decision_asset",
    "normalized_peer_mapping": "decision_asset",
    "economic_event_labels": "decision_asset",
    "dependency_intervals": "decision_asset",
    "support_coverage": "decision_asset",
    "research_record": "qualification_evidence",
    "design_review_evidence": "qualification_evidence",
    "source_review_evidence": "qualification_evidence",
    "validation_code": "qualification_evidence",
    "independent_qualification_evidence": "qualification_evidence",
    "execution_evidence": "qualification_evidence",
}
FORBIDDEN_NAMES = {"clean_daily.sqlite", "native_case_slices.json.gz", "audit_paths.csv.gz", "feature_labels.csv.gz", "product_day_opportunities.csv.gz"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def load(path: Path) -> object:
    return json.loads(path.read_text())


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def selected_source(path: Path, expected: dict | None = None) -> dict:
    assert path.is_file() and not path.is_symlink() and path.is_relative_to(LINE), path
    assert path.name not in FORBIDDEN_NAMES and "excluded_raw_audit" not in path.parts, path
    assert path.suffix not in {".db", ".sqlite", ".env", ".npy", ".png", ".h5"}, path
    actual = {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size}
    if expected:
        assert actual["sha256"] == expected["sha256"], (path, "SHA")
        expected_size = expected.get("bytes", expected.get("size_bytes"))
        assert expected_size is not None and actual["size_bytes"] == expected_size, (path, "size")
    return actual


def final_handoff() -> dict:
    path = OUT / "final_handoff.json"
    assert path.is_file(), "WAIT: root final exact inputs and authorization not delivered"
    handoff = load(path)
    assert handoff["root_authorized_final_registration"] is True
    assert handoff["all_sources_frozen"] is True
    assert handoff["stage"] == "stage051" and handoff["run_id"] == "20261018_full_opportunity_cross_session_labels_v1"
    assert handoff["final_stage051_decision"] and handoff["final_stage050_review"]
    return handoff


def finite_closure(handoff: dict) -> dict:
    checks = []
    # Only root-declared final small/normalized bindings; raw source databases,
    # native audit slices and old panels never enter this verifier.
    for declared in handoff["core_bindings"]:
        checks.append(selected_source(Path(declared["path"]), declared))
    dependencies_path = OUT / "reused_dependency_bindings.json"
    dependencies = load(dependencies_path)
    archive_manifest = Path(dependencies["archive_manifest"]["path"])
    assert digest(archive_manifest) == dependencies["archive_manifest"]["sha256"]
    for row in dependencies["dependencies"]:
        source = Path(row["source_path"])
        archived = Path(row["archive_payload_path"])
        assert source.name not in FORBIDDEN_NAMES and source.suffix in {".py", ".json", ".md"}
        assert "excluded_raw_audit" not in source.parts
        assert archived.is_relative_to(ROOT / "research/ai_assets")
        assert source.is_file() and archived.is_file() and not source.is_symlink() and not archived.is_symlink()
        assert source.stat().st_size == archived.stat().st_size == row["bytes"]
        assert digest(source) == digest(archived) == row["sha256"]
    build_manifest_path = LINE / "outputs/stage049_full_opportunity_build/experiment/manifest.json"
    build = load(build_manifest_path)
    terminal = load(LINE / "outputs/stage049_full_opportunity_build/experiment/actual_terminal.json")
    assert (build["actual_start_count"], build["completed_actual_builds"], build["native_source_queries"],
            build["actual_model_fit_calls"], build["new_cash_accounts"]) == (1, 1, 1, 0, 0)
    assert terminal["status"] == "completed" and terminal["exit_code"] == 0 and terminal["fixture"] is False
    assert (terminal["actual_start_count"], terminal["completed_actual_builds"], terminal["completed_label_rows"],
            terminal["native_source_queries"], terminal["actual_model_fit_calls"], terminal["new_cash_accounts"]) == (1, 1, 399252, 1, 0, 0)
    assert len(build["artifacts"]) == 12 and sum(row["bytes"] for row in build["artifacts"]) == 149296458
    review = load(LINE / "outputs/stage050_full_opportunity_relation_review/review_receipt.json")
    review_terminal = load(LINE / "outputs/stage050_full_opportunity_relation_review/actual_terminal.json")
    assert review["status"] == "completed" and review["findings"] == {"critical": 0, "important": 0, "minor": 0}
    assert review["manifest"]["sha256"] == digest(build_manifest_path)
    assert review["author_terminal"] == terminal
    assert (review_terminal["actual_review_starts"], review_terminal["completed_reviews"], review_terminal["exit_code"]) == (1, 1, 0)
    assert (review["labels"]["mother_rows"], review["labels"]["complete_trade_labels"],
            review["peer_mapping"]["peer_rows"], review["dependency_intervals_rows"]) == (399252, 180507, 1197457, 399252)
    assert review["financial_metrics"] is None and review["production_qualified"] is False
    assert review["peer_mapping"]["native_peer_membership_and_log_returns_full_recomputed"] is False
    fresh_facts = {
        "build_starts": 1, "completed_builds": 1, "native_source_queries": 1, "model_fits": 0, "new_cash_accounts": 0,
        "label_rows": 399252, "closed_conditional_labels": 180507, "peer_mapping_rows": 1197457,
        "required_build_outputs": 12, "required_build_bytes": 149296458,
        "review_starts": 1, "completed_reviews": 1, "review_findings": review["findings"],
        "native_review_cases": review["finite_native"]["case_count"],
        "native_peer_membership_full_recomputed": False, "financial_metrics": None, "production_qualified": False,
    }
    return {
        "schema": "stage051_finite_registration_closure_v1", "status": "passed",
        "final_core_bindings": checks, "reused_dependencies": len(dependencies["dependencies"]),
        "dependency_reference_file": selected_source(dependencies_path),
        "reported_build_and_review_scope": handoff["reported_build_and_review_scope"],
        "fresh_build_and_review_facts": fresh_facts,
        "raw_source_hashes": 0, "sql_queries": 0, "builder_calls": 0, "strategy_replays": 0, "model_fits": 0,
        "scope_limit": "本次只验最终来源、复制和有限引用闭包；不重做训练/标签构建/现金回测，也不扩大050独审所证明的范围。",
    }


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    handoff = final_handoff()
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None, declared_role: str | None = None) -> None:
        assert role in ALLOWED_ROLES, (path, role)
        row = selected_source(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage048_full_opportunity_build_protocol_v1")
        if declared_role is not None:
            row["source_declared_role"] = declared_role
        if path in rows:
            assert rows[path] == row, (path, "duplicate declaration mismatch")
        rows[path] = row

    for declared in handoff["artifacts"]:
        assert declared["reproducibility_required"] is True
        assert declared.get("raw_ohlc", False) is False
        source_role = declared["role"]
        assert source_role in REGISTRY_ROLE_MAP, (declared["path"], "undeclared registry role translation", source_role)
        add(Path(declared["path"]), REGISTRY_ROLE_MAP[source_role], declared,
            declared.get("source_declared_role", source_role))
    for name in ["registration_plan.json", "prepare_only_receipt.json", "reused_dependency_bindings.json", "final_handoff.json",
                 "stable049_inventory.json", "stable049_prepare_receipt.json", "preparation_history_terminal.json"]:
        add(OUT / name, "qualification_evidence")
    add(Path(__file__).absolute(), "qualification_evidence")
    names = [row["logical_name"] for row in rows.values()]
    collisions = {name for name, count in Counter(names).items() if count > 1}
    for path, row in rows.items():
        if row["logical_name"] in collisions:
            relative = path.relative_to(LINE)
            row["logical_name"] = str(relative.parent / ("format_" + path.suffix.lstrip(".")) / relative.with_suffix("").name)
    assert len({row["logical_name"] for row in rows.values()}) == len(rows)
    closure = finite_closure(handoff)
    dump(OUT / "finite_closure.json", closure)
    dump(OUT / "role_mapping.json", {"schema": "stage051_explicit_role_mapping_v1",
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "explicit_role_translation": REGISTRY_ROLE_MAP,
        "role_counts": dict(Counter(row["role"] for row in rows.values())),
        "excluded_assets": handoff["excluded_assets"],
        "reference_dependencies_not_repeated_as_payload": "042原语源码、041经济投影/合同/receipt复用既存Stage044实体，显式校验引用。"})
    add(OUT / "finite_closure.json", "qualification_evidence")
    add(OUT / "role_mapping.json", "qualification_evidence")
    index_before = git("ls-files", "--stage")
    (OUT / "index_before.txt").write_text(index_before)
    dump(OUT / "registration_request.json", {"schema": "stage051_exact_local_registration_request_v1",
        "created_at": stamp(), "line_id": LINE.name, "stage": "stage051",
        "run_id": "20261018_full_opportunity_cross_session_labels_v1", "destination": str(DEST),
        "source_commit": git("rev-parse", "HEAD").strip(),
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "request_self_included_without_recursive_digest": True,
        "final_authorization_binding": selected_source(OUT / "final_handoff.json"),
        "unrelated_index_sha256_before": hashlib.sha256(index_before.encode()).hexdigest(),
        "excluded_assets": handoff["excluded_assets"], "raw_market_data_copied": False,
        "new_builder_calls": 0, "sql_queries": 0, "model_fits": 0, "financial_runs": 0,
        "commit": False, "push": False, "production_changes": False})
    print(json.dumps({"status": "prepared", "payload_count_with_request": len(rows)+1,
        "payload_bytes_without_request": sum(row["size_bytes"] for row in rows.values()),
        "request_sha256": digest(OUT / "registration_request.json")}, ensure_ascii=False))


def register() -> None:
    handoff = final_handoff()
    finite_closure(handoff)
    request = load(OUT / "registration_request.json")
    assert request["final_authorization_binding"]["sha256"] == digest(OUT / "final_handoff.json")
    artifacts = []
    for row in request["artifacts"]:
        path = Path(row["path"])
        selected_source(path, row)
        artifacts.append(AiArtifact(path, row["logical_name"], row["role"], True, row["feature_schema_version"]))
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage051_local_registration/registration_request", "qualification_evidence", True))
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage051",
        run_id="20261018_full_opportunity_cross_session_labels_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {"schema": "stage051_local_registration_receipt_v1",
        "finished_at": stamp(), "status": "registered_and_exact_staged", "destination": str(result.destination),
        "manifest_path": str(result.manifest_path), "manifest_file_sha256": digest(result.manifest_path),
        "copied_count": len(result.copied_logical_names), "staged_count": len(result.staged_paths),
        "staged_paths": result.staged_paths, "commit": False, "push": False, "production_changes": False})
    print(json.dumps({"status": "registered_and_exact_staged", "copied_count": len(result.copied_logical_names),
        "staged_count": len(result.staged_paths), "manifest_file_sha256": digest(result.manifest_path)}, ensure_ascii=False))


def verify() -> None:
    manifest_path = DEST / "manifest.json"
    manifest = load(manifest_path)
    canonical_digest = manifest.pop("manifest_sha256")
    assert hashlib.sha256(canonical_json_bytes(manifest)).hexdigest() == canonical_digest
    prefix = DEST.relative_to(ROOT).as_posix()
    expected = {manifest_path.relative_to(ROOT).as_posix()}
    checks = []
    for row in manifest["artifacts"]:
        source = Path(row["source_path"])
        target = DEST / row["path"]
        assert row["role"] in ALLOWED_ROLES and row["reproducibility_required"] is True
        selected_source(source, row)
        assert target.is_file() and not target.is_symlink()
        assert target.stat().st_size == row["size_bytes"] and digest(target) == row["sha256"]
        expected.add(target.relative_to(ROOT).as_posix())
        checks.append({"logical_name": row["logical_name"], "sha256": row["sha256"], "bytes": row["size_bytes"]})
    staged = set(git("diff", "--cached", "--name-only", "--", prefix).splitlines())
    assert staged == expected, {"missing": sorted(expected-staged), "extra": sorted(staged-expected)}
    before = (OUT / "index_before.txt").read_text().splitlines()
    after = git("ls-files", "--stage").splitlines()
    before_outside = sorted(row for row in before if not row.split("\t", 1)[1].startswith(prefix + "/"))
    after_outside = sorted(row for row in after if not row.split("\t", 1)[1].startswith(prefix + "/"))
    assert before_outside == after_outside, "unrelated index changed"
    result = {"schema": "stage051_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
        "manifest_path": str(manifest_path), "manifest_file_sha256": digest(manifest_path), "manifest_canonical_sha256": canonical_digest,
        "payload_count": len(checks), "payload_bytes": sum(row["bytes"] for row in checks), "staged_count": len(staged),
        "role_counts": dict(Counter(row["role"] for row in manifest["artifacts"])),
        "source_and_copy_sha_size_all_match": True, "exact_staged_prefix_matches": True,
        "unrelated_index_entries_preserved": True,
        "unrelated_index_sha256": hashlib.sha256("\n".join(after_outside).encode()).hexdigest(),
        "finite_closure": finite_closure(final_handoff()), "checks": checks,
        "new_builder_calls": 0, "sql_queries": 0, "model_fits": 0, "financial_runs": 0,
        "commit": False, "push": False, "production_changes": False}
    dump(OUT / "final_verification.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "register", "verify"])
    args = parser.parse_args()
    {"prepare": prepare, "register": register, "verify": verify}[args.mode]()
