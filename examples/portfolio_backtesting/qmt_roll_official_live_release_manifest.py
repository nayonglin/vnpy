from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable, Mapping

from qmt_roll_official_live_execution_ledger import (
    INTENT_FINGERPRINT_VERSION_V2,
    LEDGER_SCHEMA_VERSION,
)
from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile


RELEASE_MANIFEST_SCHEMA_VERSION = 2
REQUIRED_V2_READER_CAPABILITY = "intent_fingerprint_v2"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_MANIFEST_FIELDS = {
    "schema_version",
    "release_id",
    "execution_profile",
    "official_version",
    "capital",
    "capital_label",
    "strategy_semantics_qualification",
    "source_commit",
    "critical_files",
    "tree_fingerprint",
    "ledger_contract",
    "allowed_runtime_profiles",
    "created_at_utc",
    "manifest_sha256",
}


class ReleaseManifestError(ValueError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReleaseManifestError(f"release_manifest_not_canonical:{exc}") from exc


def release_manifest_digest(payload: Mapping[str, Any]) -> str:
    core = {key: value for key, value in payload.items() if key != "manifest_sha256"}
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def serialize_release_manifest(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _critical_file_rows(
    *,
    repo_root: Path,
    critical_files: Iterable[str | Path],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in critical_files:
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise ReleaseManifestError(f"critical_file_path_invalid:{raw}")
        candidate = repo_root / relative
        if candidate.is_symlink():
            raise ReleaseManifestError(f"critical_file_symlink_forbidden:{relative}")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(repo_root):
            raise ReleaseManifestError(f"critical_file_outside_repo:{relative}")
        normalized = resolved.relative_to(repo_root).as_posix()
        if normalized in seen:
            raise ReleaseManifestError(f"critical_file_duplicate:{normalized}")
        seen.add(normalized)
        rows.append(
            {
                "path": normalized,
                "sha256": _sha256_file(resolved),
                "size_bytes": resolved.stat().st_size,
            }
        )
    if not rows:
        raise ReleaseManifestError("critical_files_empty")
    return sorted(rows, key=lambda item: item["path"])


def _tree_fingerprint(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_canonical_json_bytes(rows)).hexdigest()


def build_release_manifest(
    *,
    repo_root: Path | str,
    release_id: str,
    execution_profile: str,
    official_version: str,
    capital: int | float,
    capital_label: str,
    strategy_semantics_qualification: Mapping[str, Any],
    source_commit: str,
    critical_files: Iterable[str | Path],
    allowed_runtime_profiles: Iterable[str | ExecutionRuntimeProfile],
    created_at_utc: str,
    ledger_schema_version: int = LEDGER_SCHEMA_VERSION,
    intent_fingerprint_versions: Iterable[int] = (1, INTENT_FINGERPRINT_VERSION_V2),
    reader_capabilities: Iterable[str] = (REQUIRED_V2_READER_CAPABILITY,),
) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve(strict=True)
    normalized_release_id = str(release_id).strip()
    normalized_execution_profile = str(execution_profile).strip()
    normalized_version = str(official_version).strip()
    normalized_label = str(capital_label).strip()
    normalized_commit = str(source_commit).strip().lower()
    if (
        not normalized_release_id
        or not normalized_execution_profile
        or not normalized_version
        or not normalized_label
    ):
        raise ReleaseManifestError("release_manifest_identity_missing")
    qualification = dict(strategy_semantics_qualification)
    if set(qualification) != {"status", "evidence_id"}:
        raise ReleaseManifestError(
            "release_manifest_strategy_semantics_qualification_invalid"
        )
    if qualification.get("status") not in {"passed", "blocked"}:
        raise ReleaseManifestError(
            "release_manifest_strategy_semantics_qualification_invalid"
        )
    if not isinstance(qualification.get("evidence_id"), str) or not str(
        qualification["evidence_id"]
    ).strip():
        raise ReleaseManifestError(
            "release_manifest_strategy_semantics_qualification_invalid"
        )
    if type(capital) not in (int, float) or capital <= 0:
        raise ReleaseManifestError("release_manifest_capital_invalid")
    if not _COMMIT_RE.fullmatch(normalized_commit):
        raise ReleaseManifestError("release_manifest_source_commit_invalid")
    try:
        parsed_time = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseManifestError("release_manifest_created_at_invalid") from exc
    if not created_at_utc.endswith("Z") or parsed_time.utcoffset() is None:
        raise ReleaseManifestError("release_manifest_created_at_not_utc")

    profiles = sorted(
        {
            item.value if isinstance(item, ExecutionRuntimeProfile) else str(item)
            for item in allowed_runtime_profiles
        }
    )
    valid_profiles = {item.value for item in ExecutionRuntimeProfile}
    if not profiles or any(item not in valid_profiles for item in profiles):
        raise ReleaseManifestError("release_manifest_runtime_profiles_invalid")
    fingerprint_versions = sorted(set(intent_fingerprint_versions))
    if any(type(item) is not int or item <= 0 for item in fingerprint_versions):
        raise ReleaseManifestError("release_manifest_fingerprint_versions_invalid")
    capabilities = sorted({str(item).strip() for item in reader_capabilities})
    if not capabilities or any(not item for item in capabilities):
        raise ReleaseManifestError("release_manifest_reader_capabilities_invalid")
    if type(ledger_schema_version) is not int or ledger_schema_version <= 0:
        raise ReleaseManifestError("release_manifest_ledger_schema_invalid")

    critical_rows = _critical_file_rows(
        repo_root=repo,
        critical_files=critical_files,
    )
    core: dict[str, Any] = {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "release_id": normalized_release_id,
        "execution_profile": normalized_execution_profile,
        "official_version": normalized_version,
        "capital": capital,
        "capital_label": normalized_label,
        "strategy_semantics_qualification": qualification,
        "source_commit": normalized_commit,
        "critical_files": critical_rows,
        "tree_fingerprint": _tree_fingerprint(critical_rows),
        "ledger_contract": {
            "schema_version": ledger_schema_version,
            "intent_fingerprint_versions": fingerprint_versions,
            "reader_capabilities": capabilities,
        },
        "allowed_runtime_profiles": profiles,
        "created_at_utc": created_at_utc,
    }
    return {**core, "manifest_sha256": release_manifest_digest(core)}


def write_release_manifest(path: Path | str, payload: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = serialize_release_manifest(payload)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _validate_commit_ancestry(
    *,
    repo_root: Path,
    source_commit: str,
    current_commit: str,
) -> None:
    if not _COMMIT_RE.fullmatch(current_commit):
        raise ReleaseManifestError("release_manifest_current_commit_invalid")
    for commit, label in ((source_commit, "source"), (current_commit, "current")):
        verified = _git(repo_root, "rev-parse", "--verify", f"{commit}^{{commit}}")
        if verified.returncode != 0 or verified.stdout.strip() != commit:
            raise ReleaseManifestError(f"release_manifest_{label}_commit_missing")
    ancestry = _git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        source_commit,
        current_commit,
    )
    if ancestry.returncode == 1:
        raise ReleaseManifestError("release_manifest_source_not_ancestor")
    if ancestry.returncode != 0:
        raise ReleaseManifestError("release_manifest_ancestry_check_failed")


def load_and_validate_release_manifest(
    path: Path | str,
    *,
    repo_root: Path | str,
    expected_official_version: str,
    expected_capital: int | float,
    expected_capital_label: str,
    required_runtime_profile: str | ExecutionRuntimeProfile,
    current_commit: str,
    expected_execution_profile: str | None = None,
    required_reader_capabilities: Iterable[str] = (
        REQUIRED_V2_READER_CAPABILITY,
    ),
) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        raw = manifest_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(f"release_manifest_read_failed:{exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _MANIFEST_FIELDS:
        raise ReleaseManifestError("release_manifest_fields_invalid")
    if raw != serialize_release_manifest(payload):
        raise ReleaseManifestError("release_manifest_bytes_not_canonical")
    if payload.get("schema_version") != RELEASE_MANIFEST_SCHEMA_VERSION:
        raise ReleaseManifestError("release_manifest_schema_version_mismatch")
    release_id = payload.get("release_id")
    if not isinstance(release_id, str) or not release_id.strip():
        raise ReleaseManifestError("release_manifest_release_id_invalid")
    digest = payload.get("manifest_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise ReleaseManifestError("release_manifest_digest_invalid")
    if release_manifest_digest(payload) != digest:
        raise ReleaseManifestError("release_manifest_digest_mismatch")
    if payload.get("official_version") != expected_official_version:
        raise ReleaseManifestError("release_manifest_official_version_mismatch")
    execution_profile = payload.get("execution_profile")
    if not isinstance(execution_profile, str) or not execution_profile.strip():
        raise ReleaseManifestError("release_manifest_execution_profile_invalid")
    if (
        expected_execution_profile is not None
        and execution_profile != str(expected_execution_profile).strip()
    ):
        raise ReleaseManifestError("release_manifest_execution_profile_mismatch")
    if type(payload.get("capital")) not in (int, float) or payload.get("capital") != expected_capital:
        raise ReleaseManifestError("release_manifest_capital_mismatch")
    if payload.get("capital_label") != expected_capital_label:
        raise ReleaseManifestError("release_manifest_capital_label_mismatch")
    required_profile = (
        required_runtime_profile.value
        if isinstance(required_runtime_profile, ExecutionRuntimeProfile)
        else str(required_runtime_profile)
    )
    profiles = payload.get("allowed_runtime_profiles")
    valid_profiles = {item.value for item in ExecutionRuntimeProfile}
    if (
        not isinstance(profiles, list)
        or any(not isinstance(item, str) or item not in valid_profiles for item in profiles)
        or profiles != sorted(set(profiles))
        or required_profile not in profiles
    ):
        raise ReleaseManifestError("release_manifest_runtime_profile_not_allowed")
    qualification = payload.get("strategy_semantics_qualification")
    if (
        not isinstance(qualification, dict)
        or set(qualification) != {"status", "evidence_id"}
        or qualification.get("status") not in {"passed", "blocked"}
        or not isinstance(qualification.get("evidence_id"), str)
        or not qualification["evidence_id"].strip()
    ):
        raise ReleaseManifestError(
            "release_manifest_strategy_semantics_qualification_invalid"
        )
    submit_profiles = {
        ExecutionRuntimeProfile.SIMNOW.value,
        ExecutionRuntimeProfile.BROKER_TEST.value,
        ExecutionRuntimeProfile.PRODUCTION_LIVE.value,
    }
    if (
        required_profile in submit_profiles
        and qualification.get("status") != "passed"
    ):
        raise ReleaseManifestError(
            "release_manifest_strategy_semantics_unqualified"
        )
    if (
        required_profile in submit_profiles
        and execution_profile == "stage372-20w"
    ):
        raise ReleaseManifestError(
            "release_manifest_stage372_semantics_promotion_unsupported"
        )
    ledger = payload.get("ledger_contract")
    if not isinstance(ledger, dict) or set(ledger) != {
        "schema_version",
        "intent_fingerprint_versions",
        "reader_capabilities",
    }:
        raise ReleaseManifestError("release_manifest_ledger_contract_invalid")
    if ledger.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise ReleaseManifestError("release_manifest_ledger_schema_mismatch")
    fingerprint_versions = ledger.get("intent_fingerprint_versions")
    if (
        not isinstance(fingerprint_versions, list)
        or any(type(item) is not int or item <= 0 for item in fingerprint_versions)
        or fingerprint_versions != sorted(set(fingerprint_versions))
        or INTENT_FINGERPRINT_VERSION_V2 not in fingerprint_versions
    ):
        raise ReleaseManifestError("release_manifest_v2_fingerprint_missing")
    capabilities = ledger.get("reader_capabilities")
    required_capabilities = {str(item) for item in required_reader_capabilities}
    if (
        not isinstance(capabilities, list)
        or any(not isinstance(item, str) or not item for item in capabilities)
        or capabilities != sorted(set(capabilities))
        or not required_capabilities.issubset(capabilities)
    ):
        raise ReleaseManifestError("release_manifest_reader_capability_missing")

    critical_files = payload.get("critical_files")
    if not isinstance(critical_files, list) or not critical_files:
        raise ReleaseManifestError("release_manifest_critical_files_invalid")
    if any(
        not isinstance(item, dict)
        or set(item) != {"path", "sha256", "size_bytes"}
        or not isinstance(item.get("path"), str)
        or not isinstance(item.get("sha256"), str)
        or not _SHA256_RE.fullmatch(item["sha256"])
        or type(item.get("size_bytes")) is not int
        or item["size_bytes"] < 0
        for item in critical_files
    ):
        raise ReleaseManifestError("release_manifest_critical_files_invalid")
    if critical_files != sorted(critical_files, key=lambda item: item.get("path", "")):
        raise ReleaseManifestError("release_manifest_critical_files_unsorted")
    repo = Path(repo_root).expanduser().resolve(strict=True)
    expected_rows = _critical_file_rows(
        repo_root=repo,
        critical_files=[item.get("path", "") for item in critical_files],
    )
    if critical_files != expected_rows:
        raise ReleaseManifestError("release_manifest_critical_file_bytes_mismatch")
    if payload.get("tree_fingerprint") != _tree_fingerprint(expected_rows):
        raise ReleaseManifestError("release_manifest_tree_fingerprint_mismatch")
    source_commit = payload.get("source_commit")
    if not isinstance(source_commit, str) or not _COMMIT_RE.fullmatch(source_commit):
        raise ReleaseManifestError("release_manifest_source_commit_invalid")
    _validate_commit_ancestry(
        repo_root=repo,
        source_commit=source_commit,
        current_commit=str(current_commit).strip().lower(),
    )
    try:
        parsed_time = datetime.fromisoformat(
            str(payload.get("created_at_utc", "")).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ReleaseManifestError("release_manifest_created_at_invalid") from exc
    if not str(payload.get("created_at_utc", "")).endswith("Z") or parsed_time.utcoffset() is None:
        raise ReleaseManifestError("release_manifest_created_at_not_utc")
    return payload


__all__ = [
    "RELEASE_MANIFEST_SCHEMA_VERSION",
    "REQUIRED_V2_READER_CAPABILITY",
    "ReleaseManifestError",
    "build_release_manifest",
    "load_and_validate_release_manifest",
    "release_manifest_digest",
    "serialize_release_manifest",
    "write_release_manifest",
]
