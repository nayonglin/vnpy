from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np
import pandas as pd

from qmt_roll_ai_artifact_registry import AiArtifact, write_publication_request
from qmt_roll_official_ai_pool_policy import (
    OFFICIAL_AI_FIXED_PRODUCT,
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    OFFICIAL_AI_RANKED_PRODUCT_COUNT,
    OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
    official_ai_pool_snapshot_blockers,
)
from qmt_roll_official_live_lightweight_context import (
    ALL_FUTURES_MAPPING_PATH,
    CONTROL_OUTPUT_DIR,
    DATA_ASSET_DIR,
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_AI_LATEST_POOL_PATH,
    OFFICIAL_LIVE_AI_LIVE_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_AI_REPORT_PATH,
    OFFICIAL_LIVE_AI_SUMMARY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_MATERIAL_STRATEGY_VERSION,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_VERSION,
    STAGE173_SUMMARY_PATH,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification


MODEL_TAG = "stage935_official_live_monthly_ai_pool_update_v1"
OUTPUT_PREFIX = "qmt_roll_stage935_official_live_monthly_ai_pool_update"
DEFAULT_SOURCE_PREFIX = "qmt_roll_stage183_ai_source_floor35"
STAGE182_MODEL_TAG = "stage182_ai_product_pool_live_inference_v1"
STAGE182_OUTPUT_PREFIX = "qmt_roll_stage182_ai_product_pool_live_inference"
STAGE183_MODEL_TAG = "stage183_ai_product_pool_source_refresh_v1"
STAGE183_OUTPUT_PREFIX = "qmt_roll_stage183_ai_product_pool_source_refresh"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_PATH = PROJECT_ROOT / ".py311/bin/python"
PROJECT_DIR = Path(__file__).resolve().parent
STAGE173_PATH = PROJECT_DIR / "build_qmt_roll_stage173_forward_main_contract_data_update.py"
STAGE182_PATH = PROJECT_DIR / "build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py"
STAGE183_PATH = PROJECT_DIR / "build_qmt_roll_stage183_ai_product_pool_source_refresh.py"
STAGE182_SUMMARY_PATH = (
    DATA_ASSET_DIR / f"{STAGE182_OUTPUT_PREFIX}_summary_{STAGE182_MODEL_TAG}.json"
)
STAGE182_LIVE_POOL_PATH = (
    DATA_ASSET_DIR / f"{STAGE182_OUTPUT_PREFIX}_latest_pool_{STAGE182_MODEL_TAG}.csv"
)
STAGE182_LIVE_ELIGIBILITY_PATH = (
    DATA_ASSET_DIR
    / f"{STAGE182_OUTPUT_PREFIX}_eligibility_{STAGE182_MODEL_TAG}.csv"
)
STAGE182_COMBINED_ELIGIBILITY_PATH = (
    DATA_ASSET_DIR
    / f"{STAGE182_OUTPUT_PREFIX}_combined_stage78_eligibility_{STAGE182_MODEL_TAG}.csv"
)
STAGE182_REPORT_PATH = (
    DATA_ASSET_DIR / f"{STAGE182_OUTPUT_PREFIX}_report_{STAGE182_MODEL_TAG}.md"
)
STAGE183_SUMMARY_PATH = (
    DATA_ASSET_DIR / f"{STAGE183_OUTPUT_PREFIX}_summary_{STAGE183_MODEL_TAG}.json"
)
LOCK_PATH = CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}.lock"
MISSING_CALENDAR_UPDATE_REASON = "trading_calendar_stale_before_wall_clock_cutoff"
RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS = 4
BLOCKING_STATUSES = {
    "monthly_ai_pool_update_blocked",
    "monthly_ai_pool_exception",
    "monthly_ai_pool_update_needed",
    "monthly_ai_pool_locked",
}


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json"
        ),
        "report_txt": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.txt"
        ),
        "latest_summary_json": (
            CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_summary.json"
        ),
        "latest_report_txt": (
            CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_report.txt"
        ),
    }


def _stage182_paths(root: Path) -> dict[str, Path]:
    resolved = root.expanduser().resolve(strict=False)
    return {
        "live_pool": resolved / STAGE182_LIVE_POOL_PATH.name,
        "live_eligibility": resolved / STAGE182_LIVE_ELIGIBILITY_PATH.name,
        "combined_eligibility": resolved / STAGE182_COMBINED_ELIGIBILITY_PATH.name,
        "summary": resolved / STAGE182_SUMMARY_PATH.name,
        "report": resolved / STAGE182_REPORT_PATH.name,
    }


def _canonical_stage182_paths() -> dict[str, Path]:
    return {
        "live_pool": STAGE182_LIVE_POOL_PATH,
        "live_eligibility": STAGE182_LIVE_ELIGIBILITY_PATH,
        "combined_eligibility": STAGE182_COMBINED_ELIGIBILITY_PATH,
        "summary": STAGE182_SUMMARY_PATH,
        "report": STAGE182_REPORT_PATH,
    }


def _active_material_stage182_paths() -> dict[str, Path]:
    return {
        "live_pool": OFFICIAL_LIVE_AI_LATEST_POOL_PATH,
        "live_eligibility": OFFICIAL_LIVE_AI_LIVE_ELIGIBILITY_PATH,
        "combined_eligibility": OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
        "summary": OFFICIAL_LIVE_AI_SUMMARY_PATH,
        "report": OFFICIAL_LIVE_AI_REPORT_PATH,
    }


def _current_source_commit() -> str:
    process = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    commit = process.stdout.strip()
    if process.returncode != 0 or len(commit) != 40:
        raise RuntimeError("stage935_source_commit_unresolved")
    return commit


def _write_material_publication_request(
    *,
    artifacts: dict[str, Path],
    eval_date: str,
    source_max_date: str,
    training_label_cutoff: str,
    source_commit: str | None = None,
) -> Path:
    required = {
        "live_pool",
        "live_eligibility",
        "combined_eligibility",
        "summary",
        "report",
    }
    if set(artifacts) != required:
        raise RuntimeError("stage935_material_artifact_set_invalid")
    if not eval_date or not source_max_date or not training_label_cutoff:
        raise RuntimeError("stage935_material_provenance_incomplete")
    request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = (
        CONTROL_OUTPUT_DIR
        / "material-publication-requests"
        / f"{OUTPUT_PREFIX}_{eval_date}_{request_id}.json"
    )
    declarations = (
        AiArtifact(
            artifacts["live_pool"],
            "latest_pool.csv",
            "decision_asset",
            True,
            "stage182_v1",
        ),
        AiArtifact(
            artifacts["live_eligibility"],
            "live_eligibility.csv",
            "decision_asset",
            True,
            "stage182_v1",
        ),
        AiArtifact(
            artifacts["combined_eligibility"],
            "combined_eligibility.csv",
            "decision_asset",
            True,
            "stage182_v1",
        ),
        AiArtifact(
            artifacts["summary"],
            "summary.json",
            "qualification_evidence",
            True,
            "stage182_v1",
        ),
        AiArtifact(
            artifacts["report"],
            "report.md",
            "qualification_evidence",
            True,
            "stage182_v1",
        ),
    )
    return write_publication_request(
        destination=destination,
        official_version=OFFICIAL_LIVE_MATERIAL_STRATEGY_VERSION,
        generator=str(STAGE182_PATH.relative_to(PROJECT_ROOT)),
        data_cutoff=source_max_date,
        eval_date=eval_date,
        training_label_cutoff=training_label_cutoff,
        artifacts=declarations,
        source_commit=source_commit or _current_source_commit(),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).date().isoformat()


def _timestamp(value: str) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).normalize()


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _max_source_csv_date(path: Path) -> str:
    try:
        frame = pd.read_csv(
            path,
            usecols=lambda column: column in {"date", "datetime"},
        )
    except Exception:
        return ""
    for column in ("date", "datetime"):
        if column not in frame.columns:
            continue
        values = pd.to_datetime(frame[column], errors="coerce").dropna()
        if not values.empty:
            return pd.Timestamp(values.max()).date().isoformat()
    return ""


def _source_file_identity(path: Path) -> dict[str, int | str]:
    before = path.stat()
    sha256 = _sha256_file(path)
    after = path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise RuntimeError(f"source file changed while hashing: {path}")
    return {
        "size": int(after.st_size),
        "mtime_ns": int(after.st_mtime_ns),
        "sha256": sha256,
    }


def _validate_stage183_source(
    summary: dict[str, Any],
    *,
    expected_root: Path,
    resolved_target_date: str,
    source_prefix: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    expected = expected_root.expanduser().resolve(strict=False)
    target = _timestamp(resolved_target_date)
    if str(summary.get("source_prefix", "")) != source_prefix:
        blockers.append("stage183_source_prefix_mismatch")
    if _date_text(summary.get("analysis_end", "")) != resolved_target_date:
        blockers.append("stage183_analysis_end_not_resolved_target_date")

    declared_root_text = str(summary.get("artifact_root", "") or "")
    declared_root = Path(declared_root_text).expanduser().resolve(strict=False) if declared_root_text else None
    if declared_root is None or declared_root != expected:
        blockers.append("stage183_artifact_root_not_control_root")

    outputs = summary.get("outputs") or {}
    source_paths: dict[str, str] = {}
    source_identities: dict[str, dict[str, int | str]] = {}
    artifact_dates: dict[str, str] = {}
    date_keys = {
        "daily": "daily_max_date",
        "position_changes": "position_changes_max_date",
        "entry_candidate_snapshots": "entry_candidate_snapshots_max_date",
    }
    declared_dates = summary.get("artifact_dates") or {}
    declared_identities = summary.get("artifact_identities") or {}
    for name, date_key in date_keys.items():
        raw_path = str(outputs.get(name, "") or "")
        if not raw_path:
            blockers.append(f"stage183_{name}_path_missing")
            continue
        path = Path(raw_path).expanduser().resolve(strict=False)
        source_paths[name] = str(path)
        if not _path_is_within(path, expected):
            blockers.append("stage183_source_path_outside_control_root")
        if not path.is_file() or path.stat().st_size <= 0:
            blockers.append(f"stage183_{name}_missing_or_empty")
            continue
        try:
            actual_identity = _source_file_identity(path)
        except Exception:
            blockers.append(f"stage183_{name}_identity_unstable")
            continue
        source_identities[name] = actual_identity
        if declared_identities.get(name) != actual_identity:
            blockers.append(f"stage183_{name}_identity_mismatch")
        actual_date = _max_source_csv_date(path)
        artifact_dates[date_key] = actual_date
        if not actual_date:
            blockers.append(f"stage183_{name}_max_date_missing")
        if _date_text(declared_dates.get(date_key, "")) != actual_date:
            blockers.append(f"stage183_{name}_summary_date_mismatch")

    for name in ("daily", "position_changes"):
        date_key = date_keys[name]
        if artifact_dates.get(date_key, "") != resolved_target_date:
            blockers.append(f"stage183_{name}_max_date_not_resolved_target_date")

    candidate_date = _timestamp(
        artifact_dates.get("entry_candidate_snapshots_max_date", "")
    )
    if candidate_date is not None and target is not None and candidate_date > target:
        blockers.append("stage183_entry_candidate_snapshots_after_resolved_target_date")

    safety = summary.get("safety") or {}
    if safety.get("overwrites_official_stage78_eligibility") not in {False, 0}:
        blockers.append("stage183_safety_overwrites_official_enabled")
    if safety.get("real_order_enabled") not in {False, 0}:
        blockers.append("stage183_safety_real_order_enabled")

    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "validation_status": "valid" if not unique_blockers else "invalid",
        "blockers": unique_blockers,
        "expected_root": str(expected),
        "source_prefix": source_prefix,
        "resolved_target_date": resolved_target_date,
        "source_paths": source_paths,
        "source_identities": source_identities,
        "artifact_dates": artifact_dates,
    }


def _tail(text: str, limit: int = 4000) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[-limit:]


def _run_command(cmd: list[str], timeout: int) -> dict[str, Any]:
    started_at = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "elapsed_seconds": round(time.time() - started_at, 2),
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "exit_code": -1,
            "elapsed_seconds": round(time.time() - started_at, 2),
            "stdout_tail": "",
            "stderr_tail": repr(exc),
        }


def _build_stage182_command(
    *,
    source_prefix: str,
    source_dir: Path,
    output_dir: Path,
    seed_combined_eligibility_path: Path,
) -> list[str]:
    return [
        str(PYTHON_PATH),
        str(STAGE182_PATH),
        "--source-prefix",
        source_prefix,
        "--source-dir",
        str(source_dir.expanduser().resolve(strict=False)),
        "--output-dir",
        str(output_dir.expanduser().resolve(strict=False)),
        "--seed-combined-eligibility",
        str(seed_combined_eligibility_path.expanduser().resolve(strict=True)),
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_copy_file(source: Path, target: Path) -> None:
    source_path = source.expanduser().resolve(strict=True)
    target_path = target.expanduser().resolve(strict=False)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.tmp.",
        dir=str(target_path.parent),
    )
    temporary_path = Path(temporary_name)
    try:
        with source_path.open("rb") as source_handle, os.fdopen(descriptor, "wb") as target_handle:
            descriptor = -1
            for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                target_handle.write(chunk)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        os.chmod(temporary_path, source_path.stat().st_mode & 0o777)
        os.replace(temporary_path, target_path)
        _fsync_directory(target_path.parent)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _restore_combined_backup(
    *,
    backup_path: Path,
    canonical_combined: Path,
    expected_sha256: str,
    receipt: dict[str, Any],
) -> bool:
    try:
        _atomic_copy_file(backup_path, canonical_combined)
        restored_sha256 = _sha256_file(canonical_combined)
        receipt["restored_combined_sha256"] = restored_sha256
        if restored_sha256 != expected_sha256:
            receipt["rollback_status"] = "hash_mismatch"
            return False
        receipt["rollback_status"] = "restored"
        return True
    except Exception as exc:
        receipt["rollback_status"] = "failed"
        receipt["rollback_exception"] = repr(exc)
        return False


def _publish_stage182_candidate(
    *,
    candidate_paths: dict[str, Path],
    canonical_paths: dict[str, Path],
    candidate_validation: dict[str, Any],
    post_validate: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    required = {
        "live_pool",
        "live_eligibility",
        "combined_eligibility",
        "summary",
        "report",
    }
    receipt: dict[str, Any] = {
        "publication_status": "blocked_candidate_invalid",
        "rollback_status": "not_needed",
        "published_files": [],
        "candidate_validation": candidate_validation,
        "candidate_sha256": {},
        "canonical_sha256": {},
    }
    if candidate_validation.get("validation_status") != "valid":
        return receipt
    if set(candidate_paths) != required or set(canonical_paths) != required:
        receipt["publication_status"] = "blocked_bundle_paths_invalid"
        return receipt
    for name in sorted(required):
        path = candidate_paths[name]
        if not path.is_file() or path.stat().st_size <= 0:
            receipt["publication_status"] = "blocked_candidate_file_missing_or_empty"
            receipt["blocked_file"] = name
            return receipt

    canonical_combined = canonical_paths["combined_eligibility"]
    if not canonical_combined.is_file() or canonical_combined.stat().st_size <= 0:
        receipt["publication_status"] = "blocked_canonical_combined_missing_or_empty"
        return receipt
    pre_publication_combined_sha256 = _sha256_file(canonical_combined)
    receipt["pre_publication_combined_sha256"] = pre_publication_combined_sha256

    receipt["candidate_sha256"] = {
        name: _sha256_file(path) for name, path in candidate_paths.items()
    }
    backup_descriptor, backup_name = tempfile.mkstemp(
        prefix=f".{canonical_combined.name}.backup.",
        dir=str(canonical_combined.parent),
    )
    os.close(backup_descriptor)
    backup_path = Path(backup_name)
    backup_path.unlink()
    try:
        for name in ("summary", "report", "live_pool", "live_eligibility"):
            _atomic_copy_file(candidate_paths[name], canonical_paths[name])
            receipt["published_files"].append(name)

        _atomic_copy_file(canonical_combined, backup_path)
        receipt["combined_backup_path"] = str(backup_path)
        receipt["activation_attempted"] = 1
        _atomic_copy_file(
            candidate_paths["combined_eligibility"],
            canonical_combined,
        )
        receipt["published_files"].append("combined_eligibility")

        try:
            post_validation = post_validate()
        except Exception as exc:
            post_validation = {
                "validation_status": "invalid",
                "blockers": ["stage182_post_publish_validation_exception"],
                "exception": repr(exc),
            }
        receipt["post_validation"] = post_validation
        receipt["canonical_sha256"] = {
            name: _sha256_file(path) for name, path in canonical_paths.items()
        }
        hashes_match = receipt["candidate_sha256"] == receipt["canonical_sha256"]
        receipt["hashes_match"] = int(hashes_match)
        if post_validation.get("validation_status") != "valid" or not hashes_match:
            receipt["publication_status"] = "blocked_post_validation_failed"
            _restore_combined_backup(
                backup_path=backup_path,
                canonical_combined=canonical_combined,
                expected_sha256=pre_publication_combined_sha256,
                receipt=receipt,
            )
            return receipt

        receipt["publication_status"] = "published"
        try:
            backup_path.unlink()
            _fsync_directory(canonical_combined.parent)
            receipt["combined_backup_path"] = ""
        except Exception as exc:
            # Activation is already durable, hash-verified, and post-validated.
            # Backup cleanup failure must not falsely report a blocked activation.
            receipt["backup_cleanup_warning"] = repr(exc)
            receipt["combined_backup_path"] = (
                str(backup_path) if backup_path.exists() else ""
            )
        return receipt
    except Exception as exc:
        receipt["publication_status"] = "blocked_publication_exception"
        receipt["publication_exception"] = repr(exc)
        if backup_path.exists():
            _restore_combined_backup(
                backup_path=backup_path,
                canonical_combined=canonical_combined,
                expected_sha256=pre_publication_combined_sha256,
                receipt=receipt,
            )
        return receipt


def _parse_as_of(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _parse_time_minutes(value: str) -> int:
    hour, minute = str(value).split(":", 1)
    return int(hour) * 60 + int(minute)


def _previous_weekday(day: pd.Timestamp) -> pd.Timestamp:
    current = day.normalize()
    while current.weekday() >= 5:
        current -= pd.Timedelta(days=1)
    return current


@contextmanager
def _stage935_lock(enabled: bool) -> Iterator[dict[str, Any]]:
    if not enabled:
        yield {"lock_status": "lock_disabled"}
        return
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            yield {
                "lock_status": "lock_busy",
                "lock_path": str(LOCK_PATH.resolve()),
            }
            return
        handle.write(f"pid={os.getpid()} started_at={datetime.now():%Y-%m-%d %H:%M:%S}\n")
        handle.flush()
        yield {
            "lock_status": "lock_acquired",
            "lock_path": str(LOCK_PATH.resolve()),
            "lock_pid": os.getpid(),
        }
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass


def _wall_clock_cutoff_date(as_of: datetime, data_ready_time: str) -> pd.Timestamp:
    ready_minutes = _parse_time_minutes(data_ready_time)
    as_of_minutes = as_of.hour * 60 + as_of.minute
    day = pd.Timestamp(as_of.date()).normalize()
    if as_of.weekday() < 5 and as_of_minutes < ready_minutes:
        day -= pd.Timedelta(days=1)
    return _previous_weekday(day)


def _known_trading_dates() -> pd.Series:
    if not ALL_FUTURES_MAPPING_PATH.exists():
        return pd.Series(dtype="datetime64[ns]")
    frame = _read_csv(ALL_FUTURES_MAPPING_PATH)
    if frame.empty or "date" not in frame.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame["date"], errors="coerce").dropna().drop_duplicates().sort_values().reset_index(drop=True)


def _resolve_latest_completed(as_of: datetime, data_ready_time: str) -> tuple[str, dict[str, Any]]:
    cutoff = _wall_clock_cutoff_date(as_of, data_ready_time)
    trading_dates = _known_trading_dates()
    known_max = pd.Timestamp(trading_dates.iloc[-1]).normalize() if not trading_dates.empty else None
    calendar_lag_days = int((cutoff - known_max).days) if known_max is not None else None
    calendar_stale = bool(known_max is not None and known_max < cutoff)
    eligible = trading_dates[trading_dates <= cutoff]
    if not eligible.empty:
        resolved = pd.Timestamp(eligible.iloc[-1]).normalize()
        source = "main_contract_mapping_trading_calendar"
    else:
        resolved = _previous_weekday(cutoff)
        source = "weekday_fallback"
    evidence = {
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "data_ready_time": data_ready_time,
        "wall_clock_cutoff_date": cutoff.date().isoformat(),
        "trading_calendar_source": source,
        "known_trading_date_count": int(len(trading_dates)),
        "known_trading_date_max": (known_max.date().isoformat() if known_max is not None else ""),
        "calendar_lag_days": calendar_lag_days if calendar_lag_days is not None else "",
        "calendar_stale_before_cutoff": int(calendar_stale),
    }
    return resolved.date().isoformat(), evidence


def _calendar_stale_requires_update(resolver_evidence: dict[str, Any]) -> bool:
    known_max = _timestamp(str(resolver_evidence.get("known_trading_date_max", "")))
    cutoff = _timestamp(str(resolver_evidence.get("wall_clock_cutoff_date", "")))
    if known_max is None or cutoff is None:
        return False
    if known_max >= cutoff:
        return False
    # The mapping calendar is the source used to decide which month is complete.
    # Once the wall-clock cutoff has moved beyond it, especially across a month
    # boundary, using the stale calendar to declare the AI pool current is circular.
    return True


def _expected_monthly_eval_date(resolved_target_date: str) -> str:
    target = _timestamp(resolved_target_date)
    if target is None:
        return ""
    dates = _known_trading_dates()
    if dates.empty:
        return ""
    month_start = pd.Timestamp(year=target.year, month=target.month, day=1)
    completed = dates[(dates <= target) & (dates < month_start)]
    if completed.empty:
        return ""
    latest_month = pd.Timestamp(completed.iloc[-1]).to_period("M")
    month_dates = completed[completed.dt.to_period("M") == latest_month]
    if month_dates.empty:
        return ""
    return pd.Timestamp(month_dates.iloc[-1]).date().isoformat()


def _recent_monthly_eval_dates(expected_eval_date: str, lookback_months: int) -> list[str]:
    expected_ts = _timestamp(expected_eval_date)
    if expected_ts is None:
        return []
    dates = _known_trading_dates()
    if dates.empty:
        return []
    completed = dates[dates <= expected_ts].copy()
    if completed.empty:
        return []
    month_ends = (
        completed.groupby(completed.dt.to_period("M"))
        .max()
        .sort_values()
        .tail(int(lookback_months))
    )
    return [pd.Timestamp(value).date().isoformat() for value in month_ends.tolist()]


def _combined_eval_date_audit(
    expected_eval_date: str,
    combined_path: Path = STAGE182_COMBINED_ELIGIBILITY_PATH,
) -> dict[str, Any]:
    combined = _read_csv(combined_path)
    strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
    result: dict[str, Any] = {
        "path": str(combined_path),
        "exists": bool(combined_path.exists()),
        "shadow_analysis_start_date": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
        "recent_eval_date_lookback_months": RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS,
        "required_recent_eval_dates": _recent_monthly_eval_dates(
            expected_eval_date,
            RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS,
        ),
        "missing_recent_eval_dates": [],
        "invalid_row_count_eval_dates": [],
        "invalid_unique_product_eval_dates": [],
        "invalid_rank_eval_dates": [],
        "invalid_top_n_eval_dates": [],
        "missing_fixed_fu_eval_dates": [],
        "invalid_fixed_product_rank_eval_dates": [],
        "invalid_contract_eval_dates": [],
        "contract_blockers_by_eval_date": {},
        "row_counts_by_required_eval_date": {},
    }
    if combined.empty or "eval_date" not in combined.columns:
        result["missing_recent_eval_dates"] = list(result["required_recent_eval_dates"])
        return result
    if "strategy" in combined.columns:
        combined = combined[combined["strategy"].astype(str).eq(strategy)].copy()
    if combined.empty:
        result["missing_recent_eval_dates"] = list(result["required_recent_eval_dates"])
        return result
    combined["eval_date"] = pd.to_datetime(combined["eval_date"], errors="coerce").dt.date.astype(str)
    row_counts = combined.groupby("eval_date").size().to_dict()
    required_dates = list(result["required_recent_eval_dates"])
    result["row_counts_by_required_eval_date"] = {
        date: int(row_counts.get(date, 0)) for date in required_dates
    }
    result["missing_recent_eval_dates"] = [
        date for date in required_dates if int(row_counts.get(date, 0)) <= 0
    ]
    result["invalid_row_count_eval_dates"] = [
        date
        for date in required_dates
        if int(row_counts.get(date, 0)) != OFFICIAL_AI_TOTAL_PRODUCT_COUNT
    ]
    for date in required_dates:
        rows = combined[combined["eval_date"].eq(date)].copy()
        required = {"product_vt_symbol", "score_rank", "top_n"}
        if not required.issubset(rows.columns):
            snapshot_blockers = [
                "unique_product_count",
                "missing_fixed_product",
                "rank_range",
                "top_n",
                "fixed_product_rank",
            ]
        else:
            snapshot_blockers = official_ai_pool_snapshot_blockers(
                products=rows["product_vt_symbol"].tolist(),
                ranks=rows["score_rank"].tolist(),
                top_ns=rows["top_n"].tolist(),
                eval_date=date,
                score_types=(
                    rows["score_type"].tolist()
                    if "score_type" in rows.columns
                    else None
                ),
            )
        if snapshot_blockers:
            result["invalid_contract_eval_dates"].append(date)
            result["contract_blockers_by_eval_date"][date] = list(
                snapshot_blockers
            )
        if "unique_product_count" in snapshot_blockers:
            result["invalid_unique_product_eval_dates"].append(date)
        if "missing_fixed_product" in snapshot_blockers:
            result["missing_fixed_fu_eval_dates"].append(date)
        if "rank_range" in snapshot_blockers:
            result["invalid_rank_eval_dates"].append(date)
        if "top_n" in snapshot_blockers:
            result["invalid_top_n_eval_dates"].append(date)
        if "fixed_product_rank" in snapshot_blockers:
            result["invalid_fixed_product_rank_eval_dates"].append(date)
    return result


def _month_start(value: str) -> str:
    parsed = _timestamp(value)
    if parsed is None:
        return ""
    return pd.Timestamp(year=parsed.year, month=parsed.month, day=1).date().isoformat()


def _validate_stage182_outputs(
    expected_eval_date: str = "",
    *,
    paths: dict[str, Path] | None = None,
    require_official_path: bool = True,
    require_declared_outputs: bool = False,
    expected_source_paths: dict[str, str] | None = None,
    expected_source_identities: dict[str, dict[str, int | str]] | None = None,
) -> dict[str, Any]:
    selected_paths = paths or _canonical_stage182_paths()
    summary_path = selected_paths["summary"]
    live_pool_path = selected_paths["live_pool"]
    live_eligibility_path = selected_paths["live_eligibility"]
    combined_eligibility_path = selected_paths["combined_eligibility"]
    summary = _read_json(summary_path)
    blockers: list[str] = []
    warnings: list[str] = []
    eval_date = _date_text(summary.get("eval_date", ""))
    source_max_date = _date_text(summary.get("source_max_date", ""))
    top_products: list[str] = []
    strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
    required_eligibility_columns = {
        "strategy",
        "score_type",
        "eval_date",
        "product_vt_symbol",
        "score",
        "score_rank",
        "top_n",
    }
    required_live_pool_columns = {
        "strategy",
        "eval_date",
        "product_vt_symbol",
        "predicted_product_suitability_probability",
        "ai_rank",
        "selection_role",
        "source_score_type",
    }

    if not summary:
        blockers.append("stage182_summary_missing")
    elif summary.get("_read_error"):
        blockers.append("stage182_summary_read_error")
    if expected_eval_date and eval_date != expected_eval_date:
        blockers.append("stage182_eval_date_not_expected")
    if not eval_date:
        blockers.append("stage182_eval_date_missing")
    if eval_date and source_max_date:
        eval_ts = _timestamp(eval_date)
        source_ts = _timestamp(source_max_date)
        if eval_ts is not None and source_ts is not None and source_ts < eval_ts:
            blockers.append("stage182_source_max_before_eval_date")

    safety = summary.get("safety") or {}
    if safety.get("overwrites_official_stage78_eligibility") not in {False, 0}:
        blockers.append("stage182_safety_overwrites_official_enabled")
    if safety.get("uses_future_label_for_eval_date") not in {False, 0}:
        blockers.append("stage182_safety_future_label_enabled")
    if safety.get("real_order_enabled") not in {False, 0}:
        blockers.append("stage182_safety_real_order_enabled")
    if require_official_path and combined_eligibility_path.resolve() != STAGE182_COMBINED_ELIGIBILITY_PATH.resolve():
        blockers.append("stage182_combined_not_canonical_publication_path")

    if require_declared_outputs:
        declared_outputs = summary.get("outputs") or {}
        for name, path in selected_paths.items():
            declared = str(declared_outputs.get(name, "") or "")
            if not declared or Path(declared).expanduser().resolve(strict=False) != path.resolve(strict=False):
                blockers.append(f"stage182_declared_{name}_path_mismatch")

    if expected_source_paths:
        declared_sources = summary.get("source_paths") or {}
        for name in ("position_changes", "entry_candidate_snapshots"):
            expected_source = str(expected_source_paths.get(name, "") or "")
            declared_source = str(declared_sources.get(name, "") or "")
            if (
                not expected_source
                or not declared_source
                or Path(expected_source).expanduser().resolve(strict=False)
                != Path(declared_source).expanduser().resolve(strict=False)
            ):
                blockers.append(f"stage182_{name}_not_stage183_validated_source")

    if expected_source_identities is not None:
        identity_names = ("position_changes", "entry_candidate_snapshots")
        expected_identities = {
            name: expected_source_identities.get(name)
            for name in identity_names
        }
        declared_identities = summary.get("source_identities") or {}
        declared_subset = {
            name: declared_identities.get(name)
            for name in identity_names
        }
        if declared_subset != expected_identities or any(
            identity is None for identity in expected_identities.values()
        ):
            blockers.append("stage182_source_identity_not_stage183_validated_source")
        if expected_source_paths:
            try:
                current_identities = {
                    name: _source_file_identity(Path(expected_source_paths[name]))
                    for name in identity_names
                }
            except Exception:
                blockers.append("stage182_source_identity_recheck_failed")
            else:
                if current_identities != expected_identities:
                    blockers.append("stage182_source_changed_after_stage183_validation")

    live_pool = _read_csv(live_pool_path)
    live_eligibility = _read_csv(live_eligibility_path)
    combined = _read_csv(combined_eligibility_path)
    if live_pool.empty:
        blockers.append("stage182_live_pool_missing_or_empty")
    if live_eligibility.empty:
        blockers.append("stage182_live_eligibility_missing_or_empty")
    if combined.empty:
        blockers.append("stage182_combined_eligibility_missing_or_empty")
    live_missing_columns = sorted(required_eligibility_columns - set(live_eligibility.columns))
    if live_missing_columns:
        blockers.append("stage182_live_eligibility_required_columns_missing")
    combined_missing_columns = sorted(required_eligibility_columns - set(combined.columns))
    if combined_missing_columns:
        blockers.append("stage182_combined_eligibility_required_columns_missing")
    live_pool_missing_columns = sorted(required_live_pool_columns - set(live_pool.columns))
    if live_pool_missing_columns:
        blockers.append("stage182_live_pool_required_columns_missing")

    live_pool_identity: list[tuple[str, int]] = []
    live_pool_rows = pd.DataFrame()
    if (
        eval_date
        and not live_pool.empty
        and not live_pool_missing_columns
    ):
        live_pool_rows = live_pool[
            live_pool["eval_date"].astype(str).eq(eval_date)
            & live_pool["strategy"].astype(str).eq(strategy)
        ].copy()
        pool_blockers = official_ai_pool_snapshot_blockers(
            products=live_pool_rows["product_vt_symbol"].tolist(),
            ranks=live_pool_rows["ai_rank"].tolist(),
            top_ns=[OFFICIAL_AI_TOTAL_PRODUCT_COUNT] * len(live_pool_rows),
            eval_date=eval_date,
            score_types=live_pool_rows["source_score_type"].tolist(),
        )
        if pool_blockers:
            blockers.append("stage182_live_pool_official_contract_invalid")
        else:
            live_pool_rows["ai_rank"] = pd.to_numeric(
                live_pool_rows["ai_rank"], errors="raise"
            ).astype(int)
            live_pool_identity = sorted(
                zip(
                    live_pool_rows["product_vt_symbol"].astype(str),
                    live_pool_rows["ai_rank"],
                    strict=False,
                )
            )
        roles = live_pool_rows.set_index("product_vt_symbol")["selection_role"].astype(str).to_dict()
        if roles.get(OFFICIAL_AI_FIXED_PRODUCT) != "fixed_fu" or any(
            role != "model_ranked"
            for product, role in roles.items()
            if product != OFFICIAL_AI_FIXED_PRODUCT
        ):
            blockers.append("stage182_live_pool_selection_role_invalid")

    live_identity: list[tuple[str, int]] = []
    if eval_date and not live_eligibility.empty and "eval_date" in live_eligibility.columns:
        rows = live_eligibility[live_eligibility["eval_date"].astype(str).eq(eval_date)].copy()
        if "strategy" in rows.columns:
            rows = rows[rows["strategy"].astype(str).eq(strategy)].copy()
        if len(rows) != OFFICIAL_AI_TOTAL_PRODUCT_COUNT:
            blockers.append("stage182_live_eligibility_eval_rows_not_official_count")
        if "product_vt_symbol" in rows.columns:
            top_products = rows.sort_values(["score_rank", "product_vt_symbol"], kind="stable")[
                "product_vt_symbol"
            ].astype(str).tolist()
            if len(set(top_products)) != len(top_products):
                blockers.append("stage182_live_eligibility_duplicate_products")
        if {"score_rank", "top_n", "product_vt_symbol"}.issubset(rows.columns):
            live_contract_blockers = official_ai_pool_snapshot_blockers(
                products=rows["product_vt_symbol"].tolist(),
                ranks=rows["score_rank"].tolist(),
                top_ns=rows["top_n"].tolist(),
                eval_date=eval_date,
                score_types=rows["score_type"].tolist(),
            )
            if live_contract_blockers:
                blockers.append("stage182_live_eligibility_official_contract_invalid")
            else:
                ranks = pd.to_numeric(rows["score_rank"], errors="raise").astype(int)
                live_identity = sorted(
                    zip(
                        rows["product_vt_symbol"].astype(str),
                        ranks,
                        strict=False,
                    )
                )

    combined_identity: list[tuple[str, int]] = []
    if eval_date and not combined.empty and "eval_date" in combined.columns:
        combined_rows = combined[combined["eval_date"].astype(str).eq(eval_date)].copy()
        if "strategy" in combined_rows.columns:
            combined_rows = combined_rows[
                combined_rows["strategy"].astype(str).eq(strategy)
            ].copy()
        if combined_rows.empty:
            blockers.append("stage182_combined_missing_eval_date_rows")
        if len(combined_rows) != OFFICIAL_AI_TOTAL_PRODUCT_COUNT:
            blockers.append("stage182_combined_eval_rows_not_official_count")
        if "product_vt_symbol" in combined_rows.columns:
            combined_products = combined_rows["product_vt_symbol"].astype(str).tolist()
            if len(set(combined_products)) != len(combined_products):
                blockers.append("stage182_combined_duplicate_products")
        if {"score_rank", "top_n", "product_vt_symbol"}.issubset(combined_rows.columns):
            combined_contract_blockers = official_ai_pool_snapshot_blockers(
                products=combined_rows["product_vt_symbol"].tolist(),
                ranks=combined_rows["score_rank"].tolist(),
                top_ns=combined_rows["top_n"].tolist(),
                eval_date=eval_date,
                score_types=combined_rows["score_type"].tolist(),
            )
            if combined_contract_blockers:
                blockers.append("stage182_combined_official_contract_invalid")
            else:
                combined_ranks = pd.to_numeric(
                    combined_rows["score_rank"], errors="raise"
                ).astype(int)
                combined_identity = sorted(
                    zip(
                        combined_rows["product_vt_symbol"].astype(str),
                        combined_ranks,
                        strict=False,
                    )
                )
    if live_identity and combined_identity != live_identity:
        blockers.append("stage182_combined_current_official_pool_mismatch")
    if live_pool_identity and live_pool_identity != live_identity:
        blockers.append("stage182_live_pool_current_official_pool_mismatch")
    if live_pool_identity and live_identity:
        score_compare = live_pool_rows[
            ["product_vt_symbol", "predicted_product_suitability_probability", "source_score_type"]
        ].merge(
            rows[["product_vt_symbol", "score", "score_type"]],
            on="product_vt_symbol",
            how="outer",
            validate="one_to_one",
        )
        pool_scores = pd.to_numeric(
            score_compare["predicted_product_suitability_probability"],
            errors="coerce",
        )
        eligibility_scores = pd.to_numeric(score_compare["score"], errors="coerce")
        if (
            pool_scores.isna().any()
            or eligibility_scores.isna().any()
            or not bool(
                pd.Series(
                    np.isclose(
                        pool_scores.to_numpy(),
                        eligibility_scores.to_numpy(),
                        rtol=0.0,
                        atol=1e-12,
                    )
                ).all()
            )
            or not score_compare["source_score_type"].astype(str).equals(
                score_compare["score_type"].astype(str)
            )
        ):
            blockers.append("stage182_live_pool_score_identity_mismatch")
    if top_products and OFFICIAL_AI_FIXED_PRODUCT not in top_products:
        blockers.append("stage182_official_pool_missing_fixed_product")
    combined_eval_date_audit = _combined_eval_date_audit(
        expected_eval_date,
        combined_path=combined_eligibility_path,
    )
    if combined_eval_date_audit.get("missing_recent_eval_dates"):
        blockers.append("stage182_combined_missing_recent_eval_dates")
    if combined_eval_date_audit.get("invalid_row_count_eval_dates"):
        blockers.append(
            "stage182_combined_required_eval_date_rows_not_official_count"
        )
    if combined_eval_date_audit.get("invalid_contract_eval_dates"):
        blockers.append("stage182_combined_required_eval_date_contract_invalid")
    if any(
        combined_eval_date_audit.get(key)
        for key in (
            "invalid_unique_product_eval_dates",
            "invalid_rank_eval_dates",
            "invalid_top_n_eval_dates",
            "missing_fixed_fu_eval_dates",
            "invalid_fixed_product_rank_eval_dates",
        )
    ):
        blockers.append("stage182_combined_required_eval_date_shape_invalid")

    return {
        "validation_status": "valid" if not blockers else "invalid",
        "blockers": blockers,
        "warnings": warnings,
        "eval_date": eval_date,
        "source_max_date": source_max_date,
        "top_products": top_products,
        "summary_path": str(summary_path),
        "live_pool_path": str(live_pool_path),
        "live_eligibility_path": str(live_eligibility_path),
        "combined_eligibility_path": str(combined_eligibility_path),
        "official_live_ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "combined_eval_date_audit": combined_eval_date_audit,
        "live_pool_missing_columns": live_pool_missing_columns,
        "live_missing_columns": live_missing_columns,
        "combined_missing_columns": combined_missing_columns,
    }


def _build_base_summary(args: argparse.Namespace) -> dict[str, Any]:
    as_of = _parse_as_of(str(args.as_of or ""))
    resolved_target_date, resolver_evidence = _resolve_latest_completed(as_of, str(args.data_ready_time))
    expected_eval_date = _expected_monthly_eval_date(resolved_target_date)
    current_validation = _validate_stage182_outputs(
        expected_eval_date=expected_eval_date,
        paths=_active_material_stage182_paths(),
        require_official_path=False,
    )
    current_eval_date = current_validation.get("eval_date", "")
    update_reasons: list[str] = []
    current_ts = _timestamp(str(current_eval_date))
    expected_ts = _timestamp(str(expected_eval_date))

    if _calendar_stale_requires_update(resolver_evidence):
        update_reasons.append(MISSING_CALENDAR_UPDATE_REASON)
    if not expected_eval_date:
        update_reasons.append("expected_eval_date_unresolved")
    elif current_ts is None:
        update_reasons.append("current_stage182_eval_date_missing")
    elif expected_ts is not None and current_ts < expected_ts:
        update_reasons.append("current_stage182_eval_date_stale")
    if current_validation.get("validation_status") != "valid":
        update_reasons.append("current_stage182_outputs_invalid")
    if bool(args.force):
        update_reasons.append("force_requested")

    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "mode": str(args.mode),
        "source_prefix": str(args.source_prefix),
        "data_ready_time": str(args.data_ready_time),
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "resolved_target_date": resolved_target_date,
        "expected_eval_date": expected_eval_date,
        "current_eval_date": current_eval_date,
        "current_stage182_validation": current_validation,
        "resolver_evidence": resolver_evidence,
        "update_reasons": update_reasons,
        "commands": {},
        "blockers": [],
        "warnings": list(current_validation.get("warnings") or []),
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
        "real_order_enabled": False,
        "judgement": {
            "overfit_before": "否。Stage935 只按完整月份刷新 AI 池文件，不改排序模型、策略参数或信号规则。",
            "continue_before": "是。月度 AI 池如果依赖人工刷新，会直接破坏实盘设计中的月更口径。",
            "overfit_after": "否。输出只用于执行接线和安全校验，不根据交易结果反向挑参。",
            "continue_after": "是。后续应把 Stage935 纳入自动化健康检查，确保池子 stale 时能自动修复或 fail-closed。",
        },
    }


def _mark_blocked(summary: dict[str, Any], reason: str) -> dict[str, Any]:
    blockers = list(summary.get("blockers") or [])
    blockers.append(reason)
    summary["blockers"] = blockers
    summary["automation_status"] = "monthly_ai_pool_update_blocked"
    summary["action"] = "blocked_fail_closed"
    return summary


def _execute_update(summary: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    expected_eval_date = str(summary.get("expected_eval_date") or "")
    resolved_target_date = str(summary.get("resolved_target_date") or "")
    source_prefix = str(args.source_prefix)
    if not expected_eval_date or not resolved_target_date:
        return _mark_blocked(summary, "expected_or_resolved_date_missing")
    if CONTROL_OUTPUT_DIR.expanduser().resolve(strict=False) == DATA_ASSET_DIR.expanduser().resolve(strict=False):
        return _mark_blocked(summary, "stage935_control_output_dir_not_isolated")

    data_start = _month_start(expected_eval_date)
    if MISSING_CALENDAR_UPDATE_REASON in set(summary.get("update_reasons") or []):
        data_start = _month_start(str(summary.get("resolver_evidence", {}).get("known_trading_date_max", ""))) or data_start
        wall_clock_cutoff = _date_text((summary.get("resolver_evidence") or {}).get("wall_clock_cutoff_date", ""))
        if wall_clock_cutoff:
            resolved_target_date = wall_clock_cutoff
            summary["resolved_target_date"] = resolved_target_date
            summary["calendar_stale_recovery_target_date"] = resolved_target_date
    if not bool(args.skip_data_update):
        stage173_cmd = [
            str(PYTHON_PATH),
            str(STAGE173_PATH),
            "--mapping-start",
            data_start,
            "--bar-start",
            data_start,
            "--end",
            resolved_target_date,
        ]
        stage173_result = _run_command(stage173_cmd, timeout=int(args.data_update_timeout_seconds))
        summary["commands"]["stage173_data_update"] = stage173_result
        if stage173_result.get("exit_code") != 0:
            return _mark_blocked(summary, "stage173_data_update_failed")
        stage173_summary = _read_json(STAGE173_SUMMARY_PATH)
        summary["stage173_summary"] = {
            "path": str(STAGE173_SUMMARY_PATH),
            "max_saved_date": stage173_summary.get("max_saved_date", ""),
            "failed_count": stage173_summary.get("failed_count", 0),
            "empty_count": stage173_summary.get("empty_count", 0),
            "mapping_combined_max_date": (stage173_summary.get("mapping_update") or {}).get("combined_max_date", ""),
        }
        if int(stage173_summary.get("failed_count", 0) or 0) > 0:
            return _mark_blocked(summary, "stage173_failed_contracts_present")
        if _date_text(stage173_summary.get("max_saved_date", "")) != resolved_target_date:
            return _mark_blocked(summary, "stage173_max_saved_date_not_resolved_target_date")
        if MISSING_CALENDAR_UPDATE_REASON in set(summary.get("update_reasons") or []):
            refreshed_target_date, refreshed_evidence = _resolve_latest_completed(
                _parse_as_of(str(args.as_of or "")),
                str(args.data_ready_time),
            )
            refreshed_expected = _expected_monthly_eval_date(refreshed_target_date)
            summary["post_stage173_resolver_evidence"] = refreshed_evidence
            summary["resolved_target_date"] = refreshed_target_date
            summary["expected_eval_date"] = refreshed_expected
            expected_eval_date = refreshed_expected
            resolved_target_date = refreshed_target_date
            if not expected_eval_date:
                return _mark_blocked(summary, "expected_eval_date_unresolved_after_stage173")

    stage183_cmd = [
        str(PYTHON_PATH),
        str(STAGE183_PATH),
        "--analysis-end",
        resolved_target_date,
        "--source-prefix",
        source_prefix,
    ]
    stage183_result = _run_command(stage183_cmd, timeout=int(args.source_refresh_timeout_seconds))
    summary["commands"]["stage183_source_refresh"] = stage183_result
    if stage183_result.get("exit_code") != 0:
        return _mark_blocked(summary, "stage183_source_refresh_failed")

    stage183_summary = _read_json(STAGE183_SUMMARY_PATH)
    stage183_validation = _validate_stage183_source(
        stage183_summary,
        expected_root=CONTROL_OUTPUT_DIR,
        resolved_target_date=resolved_target_date,
        source_prefix=source_prefix,
    )
    summary["stage183_summary"] = {
        "path": str(STAGE183_SUMMARY_PATH),
        "analysis_end": stage183_summary.get("analysis_end", ""),
        "source_prefix": stage183_summary.get("source_prefix", ""),
        "artifact_root": stage183_summary.get("artifact_root", ""),
        "artifact_dates": stage183_summary.get("artifact_dates", {}),
        "artifact_identities": stage183_summary.get("artifact_identities", {}),
        "outputs": stage183_summary.get("outputs", {}),
        "safety": stage183_summary.get("safety", {}),
    }
    summary["stage183_source_validation"] = stage183_validation
    if stage183_validation.get("validation_status") != "valid":
        summary["blockers"] = list(summary.get("blockers") or []) + list(
            stage183_validation.get("blockers") or []
        )
        return _mark_blocked(summary, "stage183_source_validation_failed")

    stage182_cmd = _build_stage182_command(
        source_prefix=source_prefix,
        source_dir=CONTROL_OUTPUT_DIR,
        output_dir=CONTROL_OUTPUT_DIR,
        seed_combined_eligibility_path=OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    )
    stage182_result = _run_command(stage182_cmd, timeout=int(args.inference_timeout_seconds))
    summary["commands"]["stage182_live_inference"] = stage182_result
    if stage182_result.get("exit_code") != 0:
        return _mark_blocked(summary, "stage182_live_inference_failed")

    candidate_paths = _stage182_paths(CONTROL_OUTPUT_DIR)
    candidate_validation = _validate_stage182_outputs(
        expected_eval_date=expected_eval_date,
        paths=candidate_paths,
        require_official_path=False,
        require_declared_outputs=True,
        expected_source_paths=stage183_validation.get("source_paths") or {},
        expected_source_identities=stage183_validation.get("source_identities") or {},
    )
    summary["stage182_candidate_validation"] = candidate_validation
    if candidate_validation.get("validation_status") != "valid":
        summary["blockers"] = list(summary.get("blockers") or []) + list(
            candidate_validation.get("blockers") or []
        )
        return _mark_blocked(summary, "stage182_candidate_validation_failed")

    canonical_paths = _canonical_stage182_paths()
    publication_receipt = _publish_stage182_candidate(
        candidate_paths=candidate_paths,
        canonical_paths=canonical_paths,
        candidate_validation=candidate_validation,
        post_validate=lambda: _validate_stage182_outputs(
            expected_eval_date=expected_eval_date,
            paths=canonical_paths,
            require_official_path=True,
            expected_source_paths=stage183_validation.get("source_paths") or {},
            expected_source_identities=stage183_validation.get("source_identities") or {},
        ),
    )
    summary["stage182_publication_receipt"] = publication_receipt
    post_validation = publication_receipt.get("post_validation") or {}
    summary["post_stage182_validation"] = post_validation
    if publication_receipt.get("publication_status") != "published":
        summary["blockers"] = list(summary.get("blockers") or []) + list(
            post_validation.get("blockers") or []
        )
        return _mark_blocked(summary, "stage182_candidate_publication_failed")

    published_summary = _read_json(canonical_paths["summary"])
    request_path = _write_material_publication_request(
        artifacts=canonical_paths,
        eval_date=str(post_validation.get("eval_date") or published_summary.get("eval_date") or ""),
        source_max_date=str(
            post_validation.get("source_max_date")
            or published_summary.get("source_max_date")
            or ""
        ),
        training_label_cutoff=str(published_summary.get("training_label_cutoff") or ""),
    )

    summary["automation_status"] = "monthly_ai_pool_updated"
    summary["material_publication_status"] = "publication_required"
    summary["material_publication_request_path"] = str(request_path)
    summary["action"] = (
        "stage183_source_refresh_stage182_inference_atomic_publication_"
        "and_material_request_completed"
    )
    summary["current_eval_date"] = post_validation.get("eval_date", "")
    summary["top_products"] = post_validation.get("top_products", [])
    return summary


def _run(args: argparse.Namespace) -> dict[str, Any]:
    summary = _build_base_summary(args)
    update_reasons = list(summary.get("update_reasons") or [])
    current_validation = summary.get("current_stage182_validation") or {}
    if not update_reasons:
        summary["automation_status"] = "monthly_ai_pool_already_current"
        summary["action"] = "skipped_no_update_needed"
        summary["top_products"] = current_validation.get("top_products", [])
        return summary
    if "expected_eval_date_unresolved" in update_reasons:
        return _mark_blocked(summary, "expected_eval_date_unresolved")
    if str(args.mode) == "check":
        summary["automation_status"] = "monthly_ai_pool_update_needed"
        summary["action"] = "check_only_no_update"
        return summary
    return _execute_update(summary, args)


def _exit_code_for_status(status: str) -> int:
    return 2 if status in BLOCKING_STATUSES else 0


def _build_report(summary: dict[str, Any]) -> str:
    commands = summary.get("commands") or {}
    command_lines: list[str] = []
    for name, result in commands.items():
        command_lines.append(
            f"{name}: exit={result.get('exit_code')} elapsed={result.get('elapsed_seconds')}s"
        )
    top_products = summary.get("top_products") or (summary.get("current_stage182_validation") or {}).get("top_products") or []
    combined_audit = (
        (summary.get("post_stage182_validation") or {}).get("combined_eval_date_audit")
        or (summary.get("current_stage182_validation") or {}).get("combined_eval_date_audit")
        or {}
    )
    lines = [
        "Stage935 官方实盘月度 AI 池自动更新",
        "",
        f"生成时间：{summary.get('generated_at', '')}",
        f"状态：{summary.get('automation_status', '')}",
        f"动作：{summary.get('action', '')}",
        f"实盘版本：{summary.get('official_live_version', '')}",
        f"最新完成交易日：{summary.get('resolved_target_date', '')}",
        f"应使用 AI 池 eval_date：{summary.get('expected_eval_date', '')}",
        f"当前 Stage182 eval_date：{summary.get('current_eval_date', '')}",
        f"最近需保留月度截面：{', '.join(map(str, combined_audit.get('required_recent_eval_dates') or [])) or '未读取'}",
        f"缺失月度截面：{', '.join(map(str, combined_audit.get('missing_recent_eval_dates') or [])) or '无'}",
        f"更新原因：{';'.join(summary.get('update_reasons') or []) or '无'}",
        (
            f"Top{OFFICIAL_AI_RANKED_PRODUCT_COUNT}+"
            f"{OFFICIAL_AI_FIXED_PRODUCT.split('.', 1)[0]} 品种："
            f"{', '.join(map(str, top_products)) or '未读取'}"
        ),
        f"正式物料发布状态：{summary.get('material_publication_status', '未生成')}",
        f"正式物料发布请求：{summary.get('material_publication_request_path', '') or '无'}",
        f"阻断：{';'.join(summary.get('blockers') or []) or '无'}",
        f"警告：{';'.join(summary.get('warnings') or []) or '无'}",
        f"send order API 次数：{summary.get('send_order_api_called_count', 0)}",
        f"撤单 API 次数：{summary.get('cancel_order_api_called_count', 0)}",
        f"总 order API 次数：{summary.get('order_api_called_count', 0)}",
        "",
        "命令结果：",
        *(command_lines if command_lines else ["无"]),
        "",
        "反思：",
        f"运行前过拟合：{(summary.get('judgement') or {}).get('overfit_before', '')}",
        f"运行前继续价值：{(summary.get('judgement') or {}).get('continue_before', '')}",
        f"运行后过拟合：{(summary.get('judgement') or {}).get('overfit_after', '')}",
        f"运行后继续价值：{(summary.get('judgement') or {}).get('continue_after', '')}",
    ]
    return "\n".join(lines) + "\n"


def _should_send_email(summary: dict[str, Any], policy: str) -> bool:
    if policy == "never":
        return False
    if policy == "always":
        return True
    if policy == "updates":
        return str(summary.get("automation_status")) == "monthly_ai_pool_updated"
    return str(summary.get("automation_status")) in {
        "monthly_ai_pool_updated",
        "monthly_ai_pool_update_blocked",
        "monthly_ai_pool_update_needed",
        "monthly_ai_pool_exception",
        "monthly_ai_pool_locked",
    }


def _send_email_if_needed(summary: dict[str, Any], report: str, paths: dict[str, Path], policy: str) -> dict[str, Any]:
    if not _should_send_email(summary, policy):
        return {"email_status": "skipped_by_policy", "email_policy": policy}
    status = str(summary.get("automation_status") or "unknown")
    if status == "monthly_ai_pool_updated":
        subject_status = "已更新"
        severity = "info"
    elif status == "monthly_ai_pool_already_current":
        subject_status = "已是最新"
        severity = "info"
    else:
        subject_status = "需处理"
        severity = "warning"
    subject = (
        f"[C9/15w][AI池月更{subject_status}] "
        f"应为{summary.get('expected_eval_date', '')} 当前{summary.get('current_eval_date', '')}"
    )
    return send_official_live_email_notification(
        subject=subject,
        body=report,
        event_type="stage935_monthly_ai_pool_update",
        severity=severity,
        attachments=[paths["summary_json"], paths["report_txt"]],
        metadata={
            "automation_status": status,
            "expected_eval_date": summary.get("expected_eval_date", ""),
            "current_eval_date": summary.get("current_eval_date", ""),
            "send_order_api_called_count": summary.get("send_order_api_called_count"),
            "cancel_order_api_called_count": summary.get("cancel_order_api_called_count"),
            "order_api_called_count": summary.get("order_api_called_count"),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live monthly AI pool auto updater.")
    parser.add_argument("--mode", choices=["check", "run"], default="run")
    parser.add_argument("--as-of", default="")
    parser.add_argument("--data-ready-time", default="16:30")
    parser.add_argument("--source-prefix", default=DEFAULT_SOURCE_PREFIX)
    parser.add_argument("--skip-data-update", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--email-policy",
        choices=["changes", "updates", "always", "never"],
        default="changes",
    )
    parser.add_argument("--data-update-timeout-seconds", type=int, default=3600)
    parser.add_argument("--source-refresh-timeout-seconds", type=int, default=7200)
    parser.add_argument("--inference-timeout-seconds", type=int, default=3600)
    parser.add_argument("--disable-lock", action="store_true")
    args = parser.parse_args()

    CONTROL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    with _stage935_lock(enabled=not bool(args.disable_lock)) as lock_result:
        if lock_result.get("lock_status") == "lock_busy":
            summary = {
                "model_tag": MODEL_TAG,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "mode": str(args.mode),
                "automation_status": "monthly_ai_pool_locked",
                "action": "blocked_fail_closed_another_stage935_running",
                "blockers": ["stage935_lock_busy"],
                "warnings": [],
                "lock": lock_result,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
                "real_order_enabled": False,
            }
        else:
            try:
                summary = _run(args)
                summary["lock"] = lock_result
            except Exception as exc:
                summary = {
                    "model_tag": MODEL_TAG,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "official_live_version": OFFICIAL_LIVE_VERSION,
                    "official_live_alias": OFFICIAL_LIVE_ALIAS,
                    "mode": str(args.mode),
                    "automation_status": "monthly_ai_pool_exception",
                    "action": "exception_fail_closed",
                    "blockers": ["stage935_exception"],
                    "warnings": [],
                    "lock": lock_result,
                    "error": repr(exc),
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                    "order_api_called_count": 0,
                    "real_order_enabled": False,
                }

    report = _build_report(summary)
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_txt"].write_text(report, encoding="utf-8")
    paths["latest_summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["latest_report_txt"].write_text(report, encoding="utf-8")
    email_result = _send_email_if_needed(summary, report, paths, str(args.email_policy))
    summary["email_result"] = email_result
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["latest_summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(_exit_code_for_status(str(summary.get("automation_status", ""))))


if __name__ == "__main__":
    main()
