from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/runtime_smoke.py"
SPEC = importlib.util.spec_from_file_location("runtime_smoke", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("create table dbbardata(datetime text)")
    connection.executemany(
        "insert into dbbardata(datetime) values (?)",
        [("2022-01-01 00:00:00",), ("2022-02-01 00:00:00",)],
    )
    connection.commit()
    connection.close()


def test_sqlite_and_snapshot_audit_require_distinct_identical_copy(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    clone = tmp_path / "clone.db"
    setting = tmp_path / "vt_setting.json"
    _database(source)
    clone.write_bytes(source.read_bytes())
    setting.write_text("{}\n", encoding="utf-8")

    database = module.audit_sqlite_database(clone)
    snapshot = module.validate_runtime_snapshot(
        source,
        clone,
        setting,
        expected_database_sha256=_sha256(source),
        expected_database_size=source.stat().st_size,
        expected_setting_sha256=_sha256(setting),
        expected_bar_rows=2,
        expected_max_datetime="2022-02-01 00:00:00",
    )

    assert database == {
        "integrity_check": "ok",
        "dbbardata_rows": 2,
        "dbbardata_max_datetime": "2022-02-01 00:00:00",
    }
    assert snapshot["passed"] is True
    assert snapshot["source_inode"] != snapshot["clone_inode"]
    assert snapshot["source_sha256"] == snapshot["clone_sha256"]


def _write_output(root: Path, name: str, payload: str) -> None:
    (root / name).write_text(payload, encoding="utf-8")


def _receipt(job_id: str, predecision: str, pid: int) -> dict:
    return {
        "job_id": job_id,
        "fresh_process_pid": pid,
        "tmpdir": f"/tmp/{job_id}/tmp",
        "mplconfigdir": f"/tmp/{job_id}/mplconfig",
        "normalized_runtime_sha256": "runtime_sha",
        "wall_seconds": 10.0,
        "input_identity_pass": True,
        "campaign_file_contract_sha256": "contract",
        "execution_file_contract_sha256": "e" * 64,
        "stage819_profile_overrides_source": "campaign_snapshot",
        "checkpoint_reused": False,
        "completed_result_reused": False,
        "predecision_sha256": {
            name: predecision for name in module.PREDECISION_NAMES
        },
        "entry_candidate_boundary_gate": {
            "passed": True,
            "target_row_count": 2,
            "target_nonnull_signal_count": 2,
        },
        "internal_reconciliation_errors": {"error": 0.0},
    }


def _smoke_tree(root: Path) -> tuple[str, ...]:
    ids = ("A1", "A2", "B", "C")
    for index, job_id in enumerate(ids, start=1):
        output = root / "job_outputs" / job_id
        output.mkdir(parents=True)
        for name in module.EXPECTED_JOB_OUTPUT_FILES:
            payload = "aa" if job_id in {"A1", "A2"} else f"{job_id}-{name}"
            if name == "label.json" and job_id == "B":
                payload = "baseline-label"
            if name == "label.json" and job_id == "C":
                payload = "candidate-label"
            _write_output(output, name, payload)
        receipt = _receipt(
            job_id,
            predecision="active-predecision" if job_id in {"B", "C"} else "aa-pre",
            pid=index,
        )
        (output / "worker_receipt.json").write_text(
            json.dumps(receipt) + "\n", encoding="utf-8"
        )
    return ids


def test_smoke_evidence_requires_exact_aa_and_predecision(tmp_path: Path) -> None:
    ids = _smoke_tree(tmp_path)
    result = module.validate_smoke_evidence(
        tmp_path,
        smoke_job_ids=ids,
        aa_job_ids=("A1", "A2"),
        active_job_ids=("B", "C"),
        campaign_contract="contract",
        completed_job_gate=True,
        shared_builder_gates={job_id: True for job_id in ids},
        max_job_seconds=600.0,
    )

    assert result["passed"] is True
    assert result["gates"]["rank10_AA_outputs_exact"] is True
    assert result["gates"]["active_month_predecision_payloads_exact"] is True
    assert result["gates"]["active_challenger_label_identifiable"] is True

    (tmp_path / "job_outputs/A2/curve.csv").write_text("drift", encoding="utf-8")
    failed = module.validate_smoke_evidence(
        tmp_path,
        smoke_job_ids=ids,
        aa_job_ids=("A1", "A2"),
        active_job_ids=("B", "C"),
        campaign_contract="contract",
        completed_job_gate=True,
        shared_builder_gates={job_id: True for job_id in ids},
        max_job_seconds=600.0,
    )
    assert failed["passed"] is False
    assert failed["gates"]["rank10_AA_outputs_exact"] is False
