from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage007_cold_true_engine_ac.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage007_cold_true_engine_ac", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_manifest_is_order_stable_and_changes_with_file_content(tmp_path: Path) -> None:
    module = load_module()
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("a = 1\n")
    b.write_text("b = 2\n")
    runtime = {"python": "3.11", "packages_sha256": "abc"}

    first = module.build_identity_manifest({"b": b, "a": a}, runtime=runtime)
    reordered = module.build_identity_manifest({"a": a, "b": b}, runtime=runtime)
    a.write_text("a = 3\n")
    changed = module.build_identity_manifest({"a": a, "b": b}, runtime=runtime)

    assert first["contract_sha256"] == reordered["contract_sha256"]
    assert first["contract_sha256"] != changed["contract_sha256"]
    assert list(first["files"]) == ["a", "b"]


def test_cold_arm_guard_requires_arm_directory_to_be_absent(tmp_path: Path) -> None:
    module = load_module()
    arm = tmp_path / "A1"

    module.assert_cold_arm_output(arm)
    arm.mkdir()

    with pytest.raises(RuntimeError, match="cold_arm_output_already_exists"):
        module.assert_cold_arm_output(arm)


def test_worker_command_and_environment_force_fresh_deterministic_process(tmp_path: Path) -> None:
    module = load_module()
    command = module.worker_command(Path("/tmp/stage007.py"), "A2")
    environment = module.worker_environment({}, tmp_path)

    assert command == [sys.executable, "-B", "/tmp/stage007.py", "--worker", "A2"]
    assert environment["PYTHONHASHSEED"] == "0"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert environment["OMP_NUM_THREADS"] == "1"
    assert environment["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] == "1"
    assert environment["MPLCONFIGDIR"].startswith(str(tmp_path))
    assert environment["TMPDIR"].startswith(str(tmp_path))


def test_stage006_upstream_requires_clean_pit_and_original_c3_gate_pass() -> None:
    module = load_module()
    valid = {
        "decision": "stage006_pit_corrected_confirmed_pass_development_only",
        "pit_audit": {"violation_rows": 0, "violation_train_months": 0, "violation_folds": 0},
        "qualification": {"C3_confirmed": {"passed": True}},
        "status_scope": "development_only_not_independent_final_oos",
    }

    module.validate_stage006_upstream(valid)

    with pytest.raises(RuntimeError, match="stage006_pit_not_clean"):
        module.validate_stage006_upstream(
            {**valid, "pit_audit": {"violation_rows": 1, "violation_train_months": 1,
                                     "violation_folds": 1}}
        )


def test_stage007_contract_forbids_checkpoint_reuse_and_freezes_arm_order() -> None:
    module = load_module()

    assert module.CHECKPOINT_REUSE_ALLOWED is False
    assert module.ARM_SEQUENCE == ("A1", "A2", "C")


def test_runtime_stability_allows_import_path_growth_but_rejects_package_drift() -> None:
    module = load_module()
    expected = {
        "python_version": "3.11",
        "packages_sha256": "abc",
        "sys_path": ["/runner"],
        "environment": {"PYTHONHASHSEED": "0"},
    }
    after_import = {**expected, "sys_path": ["/production", "/runner"]}

    module.validate_runtime_stability(expected, after_import)

    with pytest.raises(RuntimeError, match="runtime_contract_changed:packages_sha256"):
        module.validate_runtime_stability(
            expected,
            {**after_import, "packages_sha256": "changed"},
        )


def test_database_boundary_parity_ignores_post_end_appends_but_detects_history_change(
    tmp_path: Path,
) -> None:
    module = load_module()
    live = tmp_path / "live.db"
    frozen = tmp_path / "frozen.db"
    schema = (
        "CREATE TABLE dbbardata ("
        "symbol TEXT, exchange TEXT, datetime TEXT, interval TEXT, volume REAL, "
        "turnover REAL, open_interest REAL, open_price REAL, high_price REAL, "
        "low_price REAL, close_price REAL)"
    )
    row = ("a", "X", "2026-08-28 00:00:00", "d", 1, 2, 3, 4, 5, 3, 4)
    for path in (live, frozen):
        connection = sqlite3.connect(path)
        connection.execute(schema)
        connection.execute("INSERT INTO dbbardata VALUES (?,?,?,?,?,?,?,?,?,?,?)", row)
        connection.commit()
        connection.close()
    connection = sqlite3.connect(live)
    connection.execute(
        "INSERT INTO dbbardata VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("a", "X", "2026-09-01 00:00:00", "d", 2, 3, 4, 5, 6, 4, 5),
    )
    connection.commit()
    connection.close()

    parity = module.database_boundary_parity(live, frozen, "2026-08-28 23:59:59")

    assert parity["passed"] is True
    assert parity["live_rows"] == parity["frozen_rows"] == 1
    assert parity["live_minus_frozen"] == parity["frozen_minus_live"] == 0

    connection = sqlite3.connect(live)
    connection.execute(
        "UPDATE dbbardata SET close_price = 99 WHERE datetime = '2026-08-28 00:00:00'"
    )
    connection.commit()
    connection.close()

    assert module.database_boundary_parity(
        live, frozen, "2026-08-28 23:59:59"
    )["passed"] is False


def test_stage006_review_receipt_must_pass_and_bind_exact_summary_sha() -> None:
    module = load_module()
    receipt = {
        "verdict": "PASS",
        "allow_development_true_engine": True,
        "reviewed_stage006_summary_sha256": "abc",
    }

    module.validate_stage006_review_receipt(receipt, expected_summary_sha256="abc")

    with pytest.raises(RuntimeError, match="stage006_review_summary_identity_drift"):
        module.validate_stage006_review_receipt(receipt, expected_summary_sha256="changed")
    with pytest.raises(RuntimeError, match="stage006_review_not_passed"):
        module.validate_stage006_review_receipt(
            {**receipt, "verdict": "FAIL"},
            expected_summary_sha256="abc",
        )
