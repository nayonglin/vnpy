"""Pure identity and evidence gates for the Stage004 account-label smoke."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping


EXPECTED_JOB_OUTPUT_FILES = frozenset(
    {
        "summary.csv",
        "label.json",
        "curve.csv",
        "combined.csv",
        "trades.csv",
        "entry_candidates.csv",
        "entry_risk.csv",
        "trade_events.csv",
    }
)
PREDECISION_NAMES = (
    "curve",
    "trades",
    "entry_candidates",
    "entry_risk",
    "trade_events",
)


class RuntimeSmokeError(RuntimeError):
    """Raised when a frozen runtime or smoke evidence contract is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_sqlite_database(path: Path) -> dict[str, Any]:
    target = Path(path).resolve()
    if not target.is_file():
        raise RuntimeSmokeError(f"database_missing:{target}")
    connection = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        integrity = str(connection.execute("pragma integrity_check").fetchone()[0])
        count, maximum = connection.execute(
            "select count(*), max(datetime) from dbbardata"
        ).fetchone()
    finally:
        connection.close()
    return {
        "integrity_check": integrity,
        "dbbardata_rows": int(count),
        "dbbardata_max_datetime": None if maximum is None else str(maximum),
    }


def validate_runtime_snapshot(
    source_database: Path,
    clone_database: Path,
    runtime_setting: Path,
    *,
    expected_database_sha256: str,
    expected_database_size: int,
    expected_setting_sha256: str,
    expected_bar_rows: int,
    expected_max_datetime: str,
) -> dict[str, Any]:
    source = Path(source_database).resolve()
    clone = Path(clone_database).resolve()
    setting = Path(runtime_setting).resolve()
    for name, path in {
        "source_database": source,
        "clone_database": clone,
        "runtime_setting": setting,
    }.items():
        if not path.is_file():
            raise RuntimeSmokeError(f"runtime_snapshot_file_missing:{name}:{path}")
    source_stat = source.stat()
    clone_stat = clone.stat()
    source_sha = sha256_file(source)
    clone_sha = sha256_file(clone)
    setting_sha = sha256_file(setting)
    database_audit = audit_sqlite_database(clone)
    gates = {
        "source_database_sha256": source_sha == expected_database_sha256,
        "clone_database_sha256": clone_sha == expected_database_sha256,
        "source_clone_sha256_exact": source_sha == clone_sha,
        "source_database_size": source_stat.st_size == int(expected_database_size),
        "clone_database_size": clone_stat.st_size == int(expected_database_size),
        "source_clone_distinct_inode": (
            source_stat.st_dev,
            source_stat.st_ino,
        )
        != (clone_stat.st_dev, clone_stat.st_ino),
        "runtime_setting_empty_identity": setting_sha == expected_setting_sha256,
        "sqlite_integrity_ok": database_audit["integrity_check"] == "ok",
        "sqlite_bar_row_count": database_audit["dbbardata_rows"]
        == int(expected_bar_rows),
        "sqlite_max_datetime": database_audit["dbbardata_max_datetime"]
        == expected_max_datetime,
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": gates,
        "source_path": str(source),
        "clone_path": str(clone),
        "runtime_setting_path": str(setting),
        "source_device": int(source_stat.st_dev),
        "source_inode": int(source_stat.st_ino),
        "clone_device": int(clone_stat.st_dev),
        "clone_inode": int(clone_stat.st_ino),
        "source_size": int(source_stat.st_size),
        "clone_size": int(clone_stat.st_size),
        "source_sha256": source_sha,
        "clone_sha256": clone_sha,
        "runtime_setting_sha256": setting_sha,
        "database_audit": database_audit,
    }


def _receipt(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeSmokeError(f"worker_receipt_not_mapping:{path}")
    return payload


def validate_smoke_evidence(
    campaign_dir: Path,
    *,
    smoke_job_ids: tuple[str, ...],
    aa_job_ids: tuple[str, str],
    active_job_ids: tuple[str, str],
    campaign_contract: str,
    completed_job_gate: bool,
    shared_builder_gates: Mapping[str, bool],
    max_job_seconds: float,
) -> dict[str, Any]:
    campaign = Path(campaign_dir)
    if len(smoke_job_ids) != 4 or set(aa_job_ids + active_job_ids) != set(smoke_job_ids):
        raise RuntimeSmokeError("smoke_job_contract_invalid")
    receipts = {
        job_id: _receipt(campaign / "job_outputs" / job_id / "worker_receipt.json")
        for job_id in smoke_job_ids
    }
    for job_id, receipt in receipts.items():
        if receipt.get("job_id") != job_id:
            raise RuntimeSmokeError(f"worker_receipt_job_id_drift:{job_id}")
    aa_file_gates = {
        name: sha256_file(campaign / "job_outputs" / aa_job_ids[0] / name)
        == sha256_file(campaign / "job_outputs" / aa_job_ids[1] / name)
        for name in sorted(EXPECTED_JOB_OUTPUT_FILES)
    }
    active_receipts = [receipts[job_id] for job_id in active_job_ids]
    active_predecision_gates = {
        name: len(
            {
                str(receipt["predecision_sha256"][name])
                for receipt in active_receipts
            }
        )
        == 1
        for name in PREDECISION_NAMES
    }
    boundary_nonempty = all(
        receipt["entry_candidate_boundary_gate"]["passed"] is True
        and int(receipt["entry_candidate_boundary_gate"]["target_row_count"]) > 0
        and int(receipt["entry_candidate_boundary_gate"]["target_row_count"])
        == int(
            receipt["entry_candidate_boundary_gate"][
                "target_nonnull_signal_count"
            ]
        )
        for receipt in active_receipts
    )
    reconciliation_exact = all(
        max(
            abs(float(value))
            for value in receipt["internal_reconciliation_errors"].values()
        )
        <= 1e-9
        for receipt in receipts.values()
    )
    runtime_hashes = {
        str(receipt["normalized_runtime_sha256"]) for receipt in receipts.values()
    }
    isolation_exact = (
        len({int(receipt["fresh_process_pid"]) for receipt in receipts.values()}) == 4
        and len({str(receipt["tmpdir"]) for receipt in receipts.values()}) == 4
        and len({str(receipt["mplconfigdir"]) for receipt in receipts.values()}) == 4
    )
    timeout_and_identity = all(
        float(receipt["wall_seconds"]) <= float(max_job_seconds)
        and receipt.get("input_identity_pass") is True
        and receipt.get("campaign_file_contract_sha256") == campaign_contract
        and len(str(receipt.get("execution_file_contract_sha256", ""))) == 64
        and receipt.get("stage819_profile_overrides_source") == "campaign_snapshot"
        and receipt.get("checkpoint_reused") is False
        and receipt.get("completed_result_reused") is False
        and shared_builder_gates.get(job_id) is True
        for job_id, receipt in receipts.items()
    )
    active_label_identifiable = sha256_file(
        campaign / "job_outputs" / active_job_ids[0] / "label.json"
    ) != sha256_file(campaign / "job_outputs" / active_job_ids[1] / "label.json")
    gates = {
        "four_smoke_jobs_complete_and_fixed_outputs": bool(completed_job_gate),
        "rank10_AA_outputs_exact": bool(all(aa_file_gates.values())),
        "active_month_predecision_payloads_exact": bool(
            all(active_predecision_gates.values())
        ),
        "active_month_boundary_nonempty_and_complete": bool(boundary_nonempty),
        "curve_combined_trades_reconciliation_exact": bool(reconciliation_exact),
        "normalized_runtime_exact": len(runtime_hashes) == 1,
        "pid_tmp_mpl_isolation_exact": bool(isolation_exact),
        "timeout_execution_identity_and_no_reuse": bool(timeout_and_identity),
        "active_challenger_label_identifiable": bool(active_label_identifiable),
        "development_labels_not_published": not (
            campaign / "development_labels.csv"
        ).exists(),
    }
    return {
        "passed": bool(all(gates.values())),
        "gates": gates,
        "AA_file_gates": aa_file_gates,
        "active_predecision_gates": active_predecision_gates,
        "normalized_runtime_sha256": (
            next(iter(runtime_hashes)) if len(runtime_hashes) == 1 else None
        ),
        "receipt_sha256": {
            job_id: sha256_file(
                campaign / "job_outputs" / job_id / "worker_receipt.json"
            )
            for job_id in smoke_job_ids
        },
    }
