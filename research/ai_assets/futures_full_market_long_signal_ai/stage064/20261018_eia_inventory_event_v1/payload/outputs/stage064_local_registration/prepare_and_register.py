"""Stage064 最终交付后才允许登记；准备期间绝不复制半成品或暂存 Git。"""
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
OUT = LINE / "outputs/stage064_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage064/20261018_eia_inventory_event_v1"
sys.path.insert(0, str(ROOT / "examples/portfolio_backtesting"))
from qmt_roll_ai_artifact_registry import AiArtifact, register_experiment_artifacts
from qmt_roll_strategy_material_manifest import canonical_json_bytes

ALLOWED_ROLES = {"decision_asset", "model_artifact", "feature_contract", "qualification_evidence"}
REGISTRY_ROLE_MAP = {
    "decision_asset": "decision_asset", "model_artifact": "model_artifact",
    "feature_contract": "feature_contract", "qualification_evidence": "qualification_evidence",
    "portable_model": "model_artifact", "training_weights_and_intervals": "model_artifact",
    "training_scaler": "model_artifact", "predictions": "decision_asset",
    "normalized_common_model_input": "decision_asset", "normalized_common_identity": "feature_contract",
    "runtime_versions": "qualification_evidence", "fit_receipt": "qualification_evidence",
    "experiment_source": "feature_contract", "contract_tests": "feature_contract",
    "research_record": "qualification_evidence", "design_review_evidence": "qualification_evidence",
    "source_review_evidence": "qualification_evidence", "validation_code": "qualification_evidence",
    "independent_qualification_evidence": "qualification_evidence", "execution_evidence": "qualification_evidence",
    "economic_event_labels": "decision_asset", "feature_matrix": "decision_asset",
    "normalized_peer_mapping": "decision_asset", "dependency_intervals": "decision_asset", "support_coverage": "decision_asset",
    "independent_review_source": "qualification_evidence",
    "independent_description_source": "qualification_evidence",
    "independent_review_receipt": "qualification_evidence",
    "saved_model_description": "decision_asset",
    "protocol_preflight": "qualification_evidence", "source_preflight": "qualification_evidence",
    "independent_review_decision": "decision_asset", "stage_record": "qualification_evidence",
    "normalized_official_release_calendar": "decision_asset",
    "normalized_reproducibility_input_three_inventory_components": "decision_asset",
    "causal_full_calendar_scalar_and_past_sham": "decision_asset",
    "unique_decision_date_causal_external_input_all_families": "decision_asset",
    "source_coverage_and_unknown_receipt": "qualification_evidence", "source_annual_coverage": "qualification_evidence",
    "public_source_hash_header_and_status_bindings": "qualification_evidence",
    "complete_actual_source_progress": "qualification_evidence", "actual_execution_terminal": "qualification_evidence",
    "new_behavior_red_evidence": "qualification_evidence", "new_behavior_green_evidence": "qualification_evidence",
    "frozen_protocol": "feature_contract", "official_index_acquisition_receipt": "qualification_evidence",
    "accepted_two_csv_cache_bindings": "qualification_evidence", "implementation_contract": "feature_contract",
    "new_behavior_contract_tests": "feature_contract", "normal_equation_audit": "model_artifact",
    "normalized_model_input_projection": "decision_asset", "full_mother_predictions": "decision_asset",
    "full_mother_event_action_and_reference_linkage": "decision_asset", "complete_research_cash_ledger": "decision_asset",
    "paired_shared_block_inference": "decision_asset", "all_family_cash_attribution": "decision_asset",
    "unchanged_official_release_calendar": "decision_asset",
    "normalized_three_inventory_components_with_precision_recovery": "decision_asset",
    "two_layer_source_coverage": "qualification_evidence",
    "source_annual_coverage_and_precision_recovery": "qualification_evidence",
    "two_layer_public_source_status_and_hash_bindings": "qualification_evidence",
    "report_and_cell_printed_precision_residual_bound_and_original_rejection_audit": "decision_asset",
    "offline_normalization_actual_terminal": "qualification_evidence",
    "frozen_precision_input_correction_contract": "feature_contract",
    "immutable_original_source_actual_manifest": "qualification_evidence",
    "unchanged_calendar_clock_ordinal52_sham_semantics": "feature_contract",
    "precision_correction_implementation": "feature_contract",
    "precision_correction_new_behavior_tests": "feature_contract",
    "new_behavior_tests": "feature_contract",
    "first_failed_review_source_snapshot": "qualification_evidence",
    "phase_evidence": "qualification_evidence",
}

FORBIDDEN_NAMES = {"clean_daily.sqlite", "native_case_slices.json.gz", "audit_paths.csv.gz", "feature_labels.csv.gz", "product_day_opportunities.csv.gz", "trading_dates.npy"}


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
    assert path.name not in FORBIDDEN_NAMES and "excluded_raw_audit" not in path.parts and "excluded_raw_sources" not in path.parts, path
    assert path.suffix not in {".db", ".sqlite", ".env", ".png", ".h5", ".html", ".htm", ".pdf", ".xls", ".xlsx"}, path
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
    assert handoff["stage"] == "stage064" and handoff["run_id"] == "20261018_eia_inventory_event_v1"
    assert handoff["final_stage064_decision"] and handoff["final_stage063_review"]
    return handoff


def finite_closure(handoff: dict) -> dict:
    core = {}
    for declared in handoff["core_bindings"]:
        path = Path(declared["path"])
        selected_source(path, declared)
        core[str(path)] = load(path) if path.suffix == ".json" else None
    asserted = []
    for item in handoff["json_assertions"]:
        assert item["path"] in core and core[item["path"]] is not None
        value = core[item["path"]]
        for part in item["pointer"].split("/")[1:]:
            token = part.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
        assert value == item["expected"], (item["path"], item["pointer"], value, item["expected"])
        asserted.append({"path": item["path"], "pointer": item["pointer"], "actual": value, "passed": True})
    references_path = OUT / "accepted_dependency_references.json"
    references = load(references_path)
    manifests = {}
    for archived in references["archives"]:
        path = Path(archived["manifest_path"])
        assert path.is_relative_to(ROOT / "research/ai_assets")
        assert path.is_file() and not path.is_symlink() and path.stat().st_size == archived["bytes"]
        assert digest(path) == archived["sha256"]
        value = load(path)
        canonical = value.pop("manifest_sha256")
        assert hashlib.sha256(canonical_json_bytes(value)).hexdigest() == canonical
        manifests[str(path)] = {row["path"]: row for row in value["artifacts"]}
    for row in references["dependencies"]:
        manifest_rows = manifests[row["archive_manifest_path"]]
        inherited = manifest_rows[row["archive_payload_relative_path"]]
        assert inherited["sha256"] == row["sha256"] and inherited["size_bytes"] == row["bytes"]
        path = Path(row["archive_manifest_path"]).parent / row["archive_payload_relative_path"]
        assert path.is_file() and not path.is_symlink() and path.stat().st_size == row["bytes"]
        assert row["copy_entity_this_run"] is False
    return {"schema": "stage064_finite_registration_closure_v1", "status": "passed",
        "core_sha_size_bindings": len(core), "final_json_assertions": asserted,
        "accepted_dependency_archives_verified": len(references["archives"]),
        "accepted_dependency_payload_references": len(references["dependencies"]),
        "accepted_dependency_bytes_not_copied": sum(row["bytes"] for row in references["dependencies"]),
        "inherited_payload_validation": "已接受注册的manifest SHA+canonical、精确payload条目SHA及当前size；不重复旧149MB和28MB全文哈希，不声称这些旧实体已被本轮逐字节重验。",
        "reported_final_scope": handoff["reported_final_scope"],
        "model_fit_calls": 0, "cash_replay_calls": 0, "sql_queries": 0, "raw_source_hashes": 0,
        "scope_limit": "本登记只核最终资产及有限引用；不重做实验，也不扩大063独审范围，不以归档通过代替策略获准。"}


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    handoff = final_handoff()
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None, declared_role: str | None = None) -> None:
        assert role in ALLOWED_ROLES, (path, role)
        row = selected_source(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage059_eia_full_market_information_protocol_v1")
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
    for name in ["registration_plan.json", "prepare_only_receipt.json", "accepted_dependency_references.json",
                 "final_handoff.json", "preparation_history_terminal.json", "precision_increment_plan.json",
                 "precision_increment_prepare_receipt.json"]:
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
    dump(OUT / "role_mapping.json", {"schema": "stage064_explicit_role_mapping_v1",
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "explicit_role_translation": REGISTRY_ROLE_MAP,
        "role_counts": dict(Counter(row["role"] for row in rows.values())),
        "excluded_assets": handoff["excluded_assets"],
        "reference_dependencies_not_repeated_as_payload": "049/050/051、041/042和053prepared_common/identity以及054纯helper复用051/044/056已接受归档引用；不重复旧大源、旧Y或28MB共同X。060新normalized库存和时钟必须实体保存。"})
    add(OUT / "finite_closure.json", "qualification_evidence")
    add(OUT / "role_mapping.json", "qualification_evidence")
    index_before = git("ls-files", "--stage")
    (OUT / "index_before.txt").write_text(index_before)
    dump(OUT / "registration_request.json", {"schema": "stage064_exact_local_registration_request_v1",
        "created_at": stamp(), "line_id": LINE.name, "stage": "stage064",
        "run_id": "20261018_eia_inventory_event_v1", "destination": str(DEST),
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
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage064_local_registration/registration_request", "qualification_evidence", True))
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage064",
        run_id="20261018_eia_inventory_event_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {"schema": "stage064_local_registration_receipt_v1",
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
    result = {"schema": "stage064_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
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
