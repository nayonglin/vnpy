"""Evidence and accounting helpers for the frozen Stage005 label batch."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import pandas as pd


PREDECISION_NAMES = (
    "curve",
    "trades",
    "entry_candidates",
    "entry_risk",
    "trade_events",
)
MONEY_QUANTUM = Decimal("0.000001")


def parent_environment(
    base_environment: Mapping[str, str], tmp_root: Path
) -> dict[str, str]:
    orchestrator_root = (Path(tmp_root) / "orchestrator").resolve()
    environment = dict(base_environment)
    environment.update(
        {
            "QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR": "1",
            "MPLCONFIGDIR": str(orchestrator_root / "mplconfig"),
            "TMPDIR": str(orchestrator_root / "tmp"),
        }
    )
    return environment


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quantized_money(value: Any) -> Decimal:
    return Decimal(str(float(value))).quantize(MONEY_QUANTUM)


def quantized_money_sum(values: Sequence[Any]) -> float:
    return float(sum((_quantized_money(value) for value in values), Decimal("0")))


def quantized_money_reconciliation_error(
    *, additions: Sequence[Any], subtractions: Sequence[Any]
) -> float:
    value = sum((_quantized_money(item) for item in additions), Decimal("0"))
    value -= sum((_quantized_money(item) for item in subtractions), Decimal("0"))
    return float(value)


def write_predecision_evidence(
    payloads: Mapping[str, pd.DataFrame], output_dir: Path
) -> dict[str, str]:
    if set(payloads) != set(PREDECISION_NAMES):
        raise ValueError("predecision_payload_names_not_exact")
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name in PREDECISION_NAMES:
        path = target_dir / f"{name}.csv"
        if path.exists():
            raise FileExistsError(f"predecision_evidence_exists:{path}")
        payloads[name].to_csv(
            path,
            index=False,
            lineterminator="\n",
            date_format="%Y-%m-%dT%H:%M:%S.%f",
        )
        hashes[name] = _sha256(path)
    return hashes


def validate_predecision_evidence(
    evidence_dir: Path, receipts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    root = Path(evidence_dir)
    observed_files = {path.stem for path in root.glob("*.csv") if path.is_file()}
    file_audits: dict[str, dict[str, Any]] = {}
    for name in PREDECISION_NAMES:
        path = root / f"{name}.csv"
        raw_sha = _sha256(path) if path.is_file() else None
        receipt_hashes = {
            str(receipt.get("predecision_sha256", {}).get(name, ""))
            for receipt in receipts
        }
        file_audits[name] = {
            "path": str(path.resolve()),
            "raw_sha256": raw_sha,
            "receipt_hashes": sorted(receipt_hashes),
            "raw_file_matches_receipts": bool(
                raw_sha is not None
                and len(receipt_hashes) == 1
                and raw_sha in receipt_hashes
            ),
        }
    passed = bool(
        receipts
        and observed_files == set(PREDECISION_NAMES)
        and all(
            value["raw_file_matches_receipts"] for value in file_audits.values()
        )
    )
    return {
        "passed": passed,
        "file_count": len(observed_files),
        "receipt_count": len(receipts),
        "files": file_audits,
    }


def build_execution_scope_audit(
    *,
    jobs: pd.DataFrame,
    output_job_ids: set[str],
    worker_commands: Sequence[Sequence[str]],
    expected_worker_commands: set[tuple[str, ...]],
    artifact_paths: Sequence[Path],
    allowed_artifact_paths: set[Path],
    log_texts: Sequence[str],
    holdout_dates: set[str],
) -> dict[str, Any]:
    required = {"job_id", "eval_date", "split", "job_type"}
    missing = required - set(jobs.columns)
    if missing:
        raise ValueError(f"scope_audit_job_columns_missing:{sorted(missing)}")
    frame = jobs.copy()
    frame["job_id"] = frame["job_id"].astype(str)
    frame["eval_date"] = frame["eval_date"].astype(str)
    by_job = frame.set_index("job_id")
    holdout_jobs = set(
        frame.loc[
            frame["eval_date"].isin(holdout_dates)
            | frame["split"].astype(str).str.contains("holdout", case=False),
            "job_id",
        ]
    )
    unknown_outputs = set(output_job_ids) - set(frame["job_id"])
    holdout_outputs = set(output_job_ids) & holdout_jobs
    holdout_labels: set[str] = set()
    for raw_path in artifact_paths:
        path = Path(raw_path)
        if path.name != "label.json":
            continue
        job_id = path.parent.name
        date_token = job_id[:8]
        eval_date = (
            f"{date_token[:4]}-{date_token[4:6]}-{date_token[6:8]}"
            if len(date_token) == 8 and date_token.isdigit()
            else ""
        )
        if job_id in holdout_jobs or eval_date in holdout_dates:
            holdout_labels.add(job_id)

    exact_commands = [tuple(map(str, command)) for command in worker_commands]
    normalized_commands = [
        tuple(token.strip().lower() for token in command)
        for command in exact_commands
    ]
    training_tokens = {"train", "fit", "--train", "--fit", "--train-model"}
    model_commands = [
        command for command in normalized_commands if training_tokens & set(command)
    ]
    ctp_commands = [
        command
        for command in normalized_commands
        if any("ctp" in token for token in command)
        and any("connect" in token for token in command)
    ]
    order_commands = [
        command
        for command in normalized_commands
        if any(
            marker in token
            for token in command
            for marker in (
                "send-order",
                "send_order",
                "cancel-order",
                "cancel_order",
                "submit-order",
                "submit_order",
                "order-api",
                "order_api",
            )
        )
    ]
    model_suffixes = {".ubj", ".model", ".bst", ".pkl", ".pickle", ".joblib"}
    model_artifacts = [
        str(Path(path))
        for path in artifact_paths
        if Path(path).suffix.lower() in model_suffixes
        or "models" in {part.lower() for part in Path(path).parts}
        or (
            Path(path).suffix.lower() == ".json"
            and any(
                marker in Path(path).stem.lower()
                for marker in ("model", "ranker", "booster", "xgboost")
            )
        )
    ]
    log_lines = [
        line.strip().lower()
        for text in log_texts
        for line in str(text).splitlines()
        if line.strip()
    ]
    model_log_events = [
        line
        for line in log_lines
        if re.search(r"\b(model[_ -]?train|train(?:ing)? model|fit model|xgboost fit)\b", line)
    ]
    ctp_log_events = [
        line for line in log_lines if "ctp" in line and "connect" in line
    ]
    order_log_events = [
        line
        for line in log_lines
        if re.search(r"\b(send|submit|cancel)[_ -]?order\b|\border[_ -]?api\b", line)
    ]
    unexpected_artifacts = {
        str(Path(path).resolve())
        for path in artifact_paths
        if Path(path).resolve() not in {Path(value).resolve() for value in allowed_artifact_paths}
    }
    unexpected_commands = [
        command for command in exact_commands if command not in expected_worker_commands
    ]
    counts = {
        "holdout_job_count": len(holdout_jobs),
        "holdout_output_count": len(holdout_outputs),
        "holdout_label_count": len(holdout_labels),
        "model_training_command_count": len(model_commands),
        "model_artifact_count": len(model_artifacts),
        "model_training_log_event_count": len(model_log_events),
        "ctp_connect_command_count": len(ctp_commands),
        "ctp_connect_log_event_count": len(ctp_log_events),
        "order_command_count": len(order_commands),
        "order_log_event_count": len(order_log_events),
        "unknown_output_job_count": len(unknown_outputs),
        "unexpected_artifact_count": len(unexpected_artifacts),
        "unexpected_worker_command_count": len(unexpected_commands),
    }
    worker_command_shape_pass = bool(
        expected_worker_commands
        and expected_worker_commands.issubset(set(exact_commands))
        and all(command in expected_worker_commands for command in exact_commands)
    )
    return {
        "passed": bool(
            all(value == 0 for value in counts.values())
            and worker_command_shape_pass
            and len(output_job_ids) == len(frame)
        ),
        "counts": counts,
        "job_count": len(frame),
        "output_job_count": len(output_job_ids),
        "worker_command_count": len(normalized_commands),
        "worker_command_shape_pass": worker_command_shape_pass,
        "model_artifacts": model_artifacts,
        "unexpected_artifacts": sorted(unexpected_artifacts),
        "unexpected_worker_commands": [list(value) for value in unexpected_commands],
        "holdout_job_ids": sorted(holdout_jobs),
        "unknown_output_job_ids": sorted(unknown_outputs),
        "job_index_unique": bool(by_job.index.is_unique),
    }


def _attempt_path(campaign_dir: Path, attempt_id: str, phase: str) -> Path:
    if not re.fullmatch(r"attempt_[0-9A-Za-z_+:-]+", attempt_id):
        raise ValueError(f"invalid_attempt_id:{attempt_id}")
    if phase not in {"start", "end"}:
        raise ValueError(f"invalid_attempt_phase:{phase}")
    return Path(campaign_dir) / "attempts" / f"{attempt_id}_{phase}.json"


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            )
    except FileExistsError as exc:
        raise FileExistsError(
            f"append_only_receipt_exists:{path}"
        ) from exc


def _next_attempt_sequence(campaign_dir: Path) -> int:
    sequences: list[int] = []
    for path in sorted((Path(campaign_dir) / "attempts").glob("*_start.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        sequence = payload.get("attempt_sequence")
        if type(sequence) is not int or sequence <= 0:
            raise ValueError(f"attempt_sequence_invalid:{path}:{sequence}")
        sequences.append(sequence)
    if len(sequences) != len(set(sequences)):
        raise ValueError("attempt_sequence_duplicate")
    return max(sequences, default=0) + 1


def write_attempt_start(
    campaign_dir: Path,
    *,
    attempt_id: str,
    campaign_contract_sha256: str,
    completed_job_ids: Sequence[str],
    pending_job_ids: Sequence[str],
    worker_commands: Sequence[Sequence[str]],
) -> dict[str, Any]:
    if len(campaign_contract_sha256) != 64:
        raise ValueError("campaign_contract_sha256_invalid")
    completed = sorted({str(value) for value in completed_job_ids})
    pending = sorted({str(value) for value in pending_job_ids})
    if set(completed) & set(pending):
        raise ValueError("attempt_completed_pending_overlap")
    payload = {
        "attempt_id": attempt_id,
        "attempt_sequence": _next_attempt_sequence(campaign_dir),
        "phase": "start",
        "status": "running",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "campaign_contract_sha256": campaign_contract_sha256,
        "completed_job_ids_before": completed,
        "pending_job_ids_before": pending,
        "same_campaign_revalidated_job_count": len(completed),
        "pending_job_count": len(pending),
        "worker_commands": [list(map(str, command)) for command in worker_commands],
    }
    _write_new_json(_attempt_path(campaign_dir, attempt_id, "start"), payload)
    return payload


def write_attempt_end(
    campaign_dir: Path,
    *,
    attempt_id: str,
    status: str,
    completed_job_ids: Sequence[str],
    error: str | None,
) -> dict[str, Any]:
    if status not in {"complete", "failed"}:
        raise ValueError(f"attempt_end_status_invalid:{status}")
    start_path = _attempt_path(campaign_dir, attempt_id, "start")
    if not start_path.is_file():
        raise FileNotFoundError(f"attempt_start_missing:{start_path}")
    if status == "failed" and not error:
        raise ValueError("failed_attempt_error_required")
    payload = {
        "attempt_id": attempt_id,
        "phase": "end",
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "completed_job_ids_after": sorted(
            {str(value) for value in completed_job_ids}
        ),
        "completed_job_count_after": len(set(map(str, completed_job_ids))),
        "error": error,
    }
    _write_new_json(_attempt_path(campaign_dir, attempt_id, "end"), payload)
    return payload


def validate_run_authorization(
    authorization_path: Path,
    bindings: Mapping[str, Path],
    *,
    expected_decision: str = "ALLOW_STAGE005_BATCH",
    expected_scope: str | None = None,
    require_campaign_nonce: bool = False,
) -> dict[str, Any]:
    path = Path(authorization_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    frozen = payload.get("bindings", {})
    binding_audits: dict[str, dict[str, Any]] = {}
    exact_names = set(frozen) == set(bindings)
    for name, current_path in sorted(bindings.items()):
        resolved = Path(current_path).resolve()
        expected = frozen.get(name, {})
        current_sha = _sha256(resolved) if resolved.is_file() else None
        binding_audits[name] = {
            "path": str(resolved),
            "path_matches": expected.get("path") == str(resolved),
            "expected_sha256": expected.get("sha256"),
            "current_sha256": current_sha,
            "sha256_matches": bool(
                current_sha is not None and expected.get("sha256") == current_sha
            ),
        }
    scope_matches = bool(
        expected_scope is None or payload.get("scope") == expected_scope
    )
    campaign_nonce = payload.get("campaign_nonce")
    campaign_nonce_valid = bool(
        not require_campaign_nonce
        or (
            isinstance(campaign_nonce, str)
            and re.fullmatch(r"[0-9a-f]{64}", campaign_nonce)
        )
    )
    passed = bool(
        payload.get("decision") == expected_decision
        and scope_matches
        and campaign_nonce_valid
        and exact_names
        and all(
            audit["path_matches"] and audit["sha256_matches"]
            for audit in binding_audits.values()
        )
    )
    return {
        "passed": passed,
        "decision": payload.get("decision"),
        "scope": payload.get("scope"),
        "scope_matches": scope_matches,
        "campaign_nonce": campaign_nonce,
        "campaign_nonce_valid": campaign_nonce_valid,
        "authorization_path": str(path.resolve()),
        "authorization_sha256": _sha256(path),
        "binding_names_exact": exact_names,
        "bindings": binding_audits,
    }


def validate_structured_review_decision(
    decision_path: Path,
    review_path: Path,
    *,
    expected_decision: str = "ALLOW_STAGE005_BATCH",
) -> dict[str, Any]:
    decision_file = Path(decision_path).resolve()
    review_file = Path(review_path).resolve()
    payload = json.loads(decision_file.read_text(encoding="utf-8"))
    severity = payload.get("severity")
    severity_exact = bool(
        isinstance(severity, dict)
        and set(severity) == {"P0", "P1", "P2", "P3"}
        and all(
            type(severity[name]) is int and severity[name] >= 0
            for name in severity
        )
    )
    review_sha = _sha256(review_file) if review_file.is_file() else None
    review_binding_pass = bool(
        payload.get("review_path") == str(review_file)
        and payload.get("review_sha256") == review_sha
    )
    passed = bool(
        payload.get("decision") == expected_decision
        and severity_exact
        and severity["P0"] == 0
        and severity["P1"] == 0
        and review_binding_pass
    )
    return {
        "passed": passed,
        "decision": payload.get("decision"),
        "severity": severity,
        "severity_shape_exact": severity_exact,
        "review_binding_pass": review_binding_pass,
        "review_sha256": review_sha,
        "decision_sha256": _sha256(decision_file),
    }
