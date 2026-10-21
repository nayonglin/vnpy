"""本地保存固定跨期现金参考实验；不训练、不回测、不发布、不重写旧登记。"""
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
OUT = LINE / "outputs/stage044_local_registration"
DEST = ROOT / "research/ai_assets/futures_full_market_long_signal_ai/stage044/20261018_cross_session_reference_v1"
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
    inventory_path = LINE / "outputs/stage042_cross_session_experiment/artifact_inventory.json"
    inventory = load(inventory_path)
    assert (inventory["actual_starts"], inventory["actual_completions"], inventory["required_artifact_count"]) == (1, 1, 147)
    manifest_path = LINE / "outputs/stage042_cross_session_experiment/experiment/manifest.json"
    source_check(manifest_path, {"sha256": "f6ada95c6986e57303a0d76263f581a83dc536a3d13373b4bd1dd439cba16e47"})
    terminal_path = LINE / "outputs/stage042_cross_session_experiment/experiment/actual_terminal.json"
    source_check(terminal_path, {"sha256": "9a1a358322cc70a677fc1332f4758adfd45f38c6e21e0d0da584a18fc7f4b3ba"})
    terminal = load(terminal_path)
    assert (terminal["started_research_cash_accounts"], terminal["computed_research_cash_accounts"], terminal["completed_research_cash_accounts"]) == (18, 18, 18)
    assert (terminal["actual_model_fit_calls"], terminal["native_source_queries"], terminal["exit_code"]) == (0, 1, 0)
    assert terminal["status"] == "completed" and terminal["fixture"] is False
    receipt_path = LINE / "outputs/stage043_cross_session_cash_review/review_receipt.json"
    source_check(receipt_path, {"sha256": "d134c15386e40d774a532bcc9b79108ef327ddab8e70da09fb42d01837f23da1"})
    receipt = load(receipt_path)
    assert (receipt["critical"], receipt["important"], receipt["minor"]) == (0, 0, 0)
    assert receipt["research_cash_arithmetic_qualified"] is True
    assert receipt["broker_historical_truth_qualified"] is False and receipt["production_qualified"] is False and receipt["goal_complete"] is False
    assert (receipt["accounts_checked"], receipt["fills_checked"], receipt["daily_rows_checked"], receipt["position_rows_checked"]) == (18, 7302, 14720, 49796)
    assert receipt["source_manifest"]["sha256"] == digest(manifest_path)
    source_read = load(LINE / "outputs/stage042_cross_session_experiment/experiment/source_read_receipt.json")
    assert source_read["database_rehashed"] is False
    assert (source_read["native_source_queries"], source_read["native_contract_days"], source_read["native_epochs"]) == (1, 1552456, 9520)
    coverage_path = LINE / "outputs/stage043_cross_session_cash_review/coverage_receipt.json"
    coverage = load(coverage_path)
    assert (coverage["observed_rows"], coverage["exact_economic_observed_rows"], coverage["potential_rows"], coverage["potential_economics_unresolved"]) == (212852, 212852, 6389, 0)
    protocol = load(LINE / "outputs/stage039_cross_session_reference_protocol/protocol.json")
    for key in ["design_document", "design_review", "economic_projection", "economic_source_review"]:
        binding = protocol[key]
        source_check(Path(binding["path"]), binding)
    return {
        "source042_actual": {"actual_starts": inventory["actual_starts"], "actual_completions": inventory["actual_completions"],
                             "completed_research_cash_accounts": terminal["completed_research_cash_accounts"],
                             "actual_model_fit_calls": terminal["actual_model_fit_calls"], "native_source_queries": terminal["native_source_queries"],
                             "exit_code": terminal["exit_code"], "terminal_binding": source_check(terminal_path),
                             "manifest_binding": source_check(manifest_path), "database_rehashed": False},
        "source043_binding": source_check(receipt_path),
        "source043_findings": {"critical": receipt["critical"], "important": receipt["important"], "minor": receipt["minor"],
                               "accounts_checked": receipt["accounts_checked"], "fills_checked": receipt["fills_checked"],
                               "daily_rows_checked": receipt["daily_rows_checked"], "position_rows_checked": receipt["position_rows_checked"],
                               "research_cash_arithmetic_qualified": True, "broker_historical_truth_qualified": False,
                               "production_qualified": False, "goal_complete": False},
        "finite_economics_closure": {"coverage_receipt": source_check(coverage_path),
                                     "observed_rows": coverage["observed_rows"], "exact_economic_observed_rows": coverage["exact_economic_observed_rows"],
                                     "potential_rows": coverage["potential_rows"], "potential_economics_unresolved": 0,
                                     "independent_native_cases": len(receipt["native_bounded_review"]["cases_checked"]),
                                     "scope_limit": "复算保存现金账本与有限原价事件证据；不是第二次全OHLC策略仿真，也不是券商历史真值或收益资格。"},
    }


def prepare() -> None:
    assert not DEST.exists(), "immutable destination already exists"
    authorization = load(OUT / "final_root_authorization.json")
    assert authorization["authorized_by"] == "root"
    assert authorization["stage044_decision_sha256"] == "21bc9c04e9fd61e9843a0ddae072083bb6489bdc749979309ce57b8a3897e115"
    rows: dict[Path, dict] = {}

    def add(path: Path, role: str, expected: dict | None = None, declared_role: str | None = None) -> None:
        row = source_check(path, expected)
        row.update(logical_name=str(path.relative_to(LINE).with_suffix("")), role=role,
                   reproducibility_required=True, feature_schema_version="stage039_cross_session_reference_v1")
        if declared_role is not None:
            row["source_declared_role"] = declared_role
        if path in rows:
            assert rows[path] == row, path
        rows[path] = row

    expected_inventories = {
        42: (147, "3122117255105d153d45eb6c801df2288ca73c88dcec8c6e74178aa6fb0db9a8"),
        43: (7, "efd06e85feaa84cb58c9a6bc3529b149e25d494b186b41babce548fc91998f65"),
    }
    role_translations = []
    code_paths = {LINE / "tools/stage042_cross_session_experiment.py", LINE / "tools/test_stage042_cross_session_experiment.py"}
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
                source = Path(declared["path"])
                role = "feature_contract" if source in code_paths else declared["role"]
                if role != declared["role"]:
                    role_translations.append({"path": str(source), "source_declared_role": declared["role"], "registered_role": role,
                                              "reason": "根agent明确指定源/测试feature_contract；登记器标准角色合同不接受runtime_code。来源清单保持原样。"})
                add(source, role, declared, declared["role"])
        add(path, "feature_contract" if number == 42 else "qualification_evidence")
    draft = load(OUT / "registration_request.draft.json")
    assert draft["registrable"] is False
    # Retain the separate draft phase; it cannot be mistaken for final authority.
    for observed in draft["observed_known_assets"]:
        add(Path(observed["path"]), observed["role"], {"sha256": observed["sha256"], "bytes": observed["size_bytes"]})
    add(unique_stage(44), "decision_asset", {"sha256": "21bc9c04e9fd61e9843a0ddae072083bb6489bdc749979309ce57b8a3897e115", "bytes": 11038})
    for name in ["registration_request.draft.json", "prepare_only_receipt.json", "preparation_history_terminal.json", "final_root_authorization.json"]:
        add(OUT / name, "qualification_evidence")
    add(Path(__file__).absolute(), "qualification_evidence")
    names = [x["logical_name"] for x in rows.values()]
    duplicate_names = {name for name, count in Counter(names).items() if count > 1}
    for path, row in rows.items():
        if row["logical_name"] in duplicate_names:
            relative = path.relative_to(LINE)
            row["logical_name"] = str(relative.parent / ("format_" + path.suffix.lstrip(".")) / relative.with_suffix("").name)
    names = [x["logical_name"] for x in rows.values()]
    assert len(names) == len(set(names))
    allowed_roles = {"decision_asset", "model_artifact", "feature_contract", "qualification_evidence"}
    assert all(row["role"] in allowed_roles for row in rows.values())
    excluded_names = {"clean_daily.sqlite", "native_case_slices.json.gz", "audit_paths.csv.gz", "feature_labels.csv.gz", "product_day_opportunities.csv.gz", "ordered_history.npz"}
    assert not any(path.name in excluded_names or path.suffix in {".env", ".sqlite", ".db", ".npy", ".png"} or "excluded_raw_audit" in path.parts for path in rows)
    assert not any("research/ai_assets" in str(path) for path in rows)
    checks = fresh_checks()
    role_rows = sorted(rows.values(), key=lambda row: row["logical_name"])
    dump(OUT / "role_mapping.json", {"schema": "stage044_explicit_role_mapping_v1", "artifacts": role_rows,
        "explicit_role_translations": role_translations, "role_counts": dict(Counter(row["role"] for row in role_rows)),
        "mapping_scope": "源清单逐项显式角色；源/测试按根授权转换标准feature_contract且保留原始role；plot缓存实体及原价审计切片排除。自身与请求角色由最终manifest显式记录。"})
    dump(OUT / "finite_closure.json", {"schema": "stage044_finite_registration_closure_v1", "status": "passed", **checks,
        "declared_inventory_counts": {str(n): count for n, (count, _) in expected_inventories.items()},
        "selected_source_assets_sha_size_verified": len(rows), "raw_sources_rehashed": False,
        "closure_scope": "本轮源清单/现金输出/经济投影/协议/独审引用有限闭包；保留准备历史，旧数据库与原价panel及原价审计片只保留引用，未重读重算。",
        "sql_queries": 0, "model_fits": 0, "financial_runs": 0})
    add(OUT / "role_mapping.json", "qualification_evidence")
    add(OUT / "finite_closure.json", "qualification_evidence")
    index_before = git("ls-files", "--stage")
    dump(OUT / "registration_request.json", {
        "schema": "stage044_exact_local_registration_request_v1", "created_at": stamp(),
        "line_id": LINE.name, "stage": "stage044", "run_id": "20261018_cross_session_reference_v1",
        "destination": str(DEST), "source_commit": git("rev-parse", "HEAD").strip(),
        "artifacts": sorted(rows.values(), key=lambda row: row["logical_name"]),
        "request_self_included_as_qualification_evidence_without_recursive_self_digest": True, **checks,
        "final_root_register_authorization_present": True, "draft_prepare_history_preserved_as_separate_assets": True,
        "upstream_archives_reference_only": ["research/ai_assets/futures_full_market_long_signal_ai/stage013/20261018_fixed_day_quality_v1/manifest.json",
                                            "research/ai_assets/futures_full_market_long_signal_ai/stage036/20261018_peer_alignment_v1/manifest.json"],
        "explicit_excluded_raw_price_files": sorted(excluded_names), "raw_market_data_copied": False,
        "model_fits": 0, "financial_runs": 0, "commit": False, "push": False, "production_changes": False,
        "research_judgment": "保存一次固定跨期现金参考及独审，登记不改变策略或增加选择；现金算术合格不代表收益资格，更不代表目标达成。",
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
    artifacts.append(AiArtifact(OUT / "registration_request.json", "outputs/stage044_local_registration/registration_request", "qualification_evidence", True))
    fresh_checks()
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name, stage="stage044", run_id="20261018_cross_session_reference_v1", artifacts=artifacts)
    dump(OUT / "registration_receipt.json", {
        "schema": "stage044_local_registration_receipt_v1", "finished_at": stamp(), "status": "registered_and_exact_staged",
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
        "schema": "stage044_local_registration_final_verification_v1", "verified_at": stamp(), "status": "passed",
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
