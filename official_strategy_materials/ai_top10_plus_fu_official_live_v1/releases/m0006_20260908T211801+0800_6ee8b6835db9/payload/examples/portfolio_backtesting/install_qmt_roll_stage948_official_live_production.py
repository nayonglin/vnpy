from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import sqlite3
import stat
import subprocess
from dataclasses import dataclass
from typing import Any

from build_qmt_roll_stage179_release_manifest import (
    load_and_validate_production_qualification_evidence,
)
from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_daily_data_receipt import (
    initialize_production_database_from_sqlite_backup,
)
from qmt_roll_official_live_production_assets import (
    ProductionAssetError,
    validate_production_data_link,
    validate_production_venv_link,
)
from qmt_roll_official_live_launchd_surface import (
    KNOWN_CONFLICTING_LABELS as SHARED_KNOWN_CONFLICTING_LABELS,
    OWNED_LABEL_PREFIXES as SHARED_OWNED_LABEL_PREFIXES,
    PRODUCTION_PLIST_NAMES as SHARED_PRODUCTION_PLIST_NAMES,
    SAFE_PLIST_MODES as SHARED_SAFE_PLIST_MODES,
    classify_individual_launchctl_result,
    inspect_owned_launchd_surface as shared_inspect_owned_launchd_surface,
    validate_exact_owned_launchd_surface as shared_validate_exact_owned_launchd_surface,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    load_and_validate_release_manifest,
)
from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile
from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import (
    validate_stage179_activation_receipt,
)


PROJECT_DIR = Path(__file__).resolve().parent
MAIN_REPO = Path.home() / "Desktop/person/vnpy"
STABLE_REPO = Path.home() / "Desktop/person/vnpy_production_live"
STATE_ROOT = (
    Path.home()
    / "Library/Application Support/qmt-roll-stage179/production-live"
)
LAUNCHD_INSTALL_DIR = Path.home() / "Library/LaunchAgents"
PRODUCTION_PLIST_NAMES = (
    "local.qmt-roll.official-live.15w.c9-production-live-day-session.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-night-session.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-health.plist",
)
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
PRODUCTION_ACTIVATION_CONFIRM_TEXT = (
    "I_UNDERSTAND_THIS_LOADS_C9_15W_PRODUCTION_LAUNCHD_JOBS"
)
PLIST_ROLLBACK_SCHEMA_VERSION = 2
CONFLICTING_JOB_LABELS = (
    "local.qmt-roll.official-live.15w.c9-readonly-day-session",
    "local.qmt-roll.official-live.15w.c9-readonly-night-session",
    "local.qmt-roll.official-live.15w.c9-day-session",
    "local.qmt-roll.official-live.15w.c9-night-session",
    "local.qmt-roll.official-live.20w.stage372-day-session",
    "local.qmt-roll.official-live.20w.stage372-night-session",
    "local.qmt-roll.official-live.20w.stage372-postclose-precompute",
    "local.qmt-roll.official-live.15w.c9-readonly-postclose-precompute",
    "local.qmt-roll.official-live.15w.day-close-readonly",
    "local.qmt-roll.official-live.15w.postclose",
    "local.qmt-roll.official-live.15w.evening-report",
    "local.qmt-roll.official-live.15w.monthly-ai-pool",
    "local.qmt-roll.stage179.no-submit-direct",
    "local.qmt-roll.stage179.no-submit-supervisor",
)
OWNED_LAUNCHD_LABEL_PREFIXES = (
    "local.qmt-roll.official-live.",
    "local.qmt-roll.stage179.",
)
_OWNED_LABEL_RE = re.compile(
    r"local\.qmt-roll\.(?:official-live|stage179)\."
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}"
)
_SAFE_PREVIOUS_PLIST_MODES = {0o600, 0o640, 0o644}

if (
    PRODUCTION_PLIST_NAMES != SHARED_PRODUCTION_PLIST_NAMES
    or CONFLICTING_JOB_LABELS != SHARED_KNOWN_CONFLICTING_LABELS
    or OWNED_LAUNCHD_LABEL_PREFIXES != SHARED_OWNED_LABEL_PREFIXES
    or frozenset(_SAFE_PREVIOUS_PLIST_MODES) != SHARED_SAFE_PLIST_MODES
):
    raise RuntimeError("production_launchd_surface_constants_mismatch")


class ProductionInstallError(RuntimeError):
    pass


class ProductionActivationError(ProductionInstallError):
    def __init__(self, message: str, *, audit: dict[str, Any]) -> None:
        super().__init__(message)
        self.audit = audit


@dataclass(frozen=True, slots=True)
class ProductionInstallPaths:
    main_repo: Path
    stable_repo: Path
    state_root: Path
    launchd_install_dir: Path

    @property
    def main_venv(self) -> Path:
        return self.main_repo / ".py311"

    @property
    def main_data(self) -> Path:
        return self.main_repo / "examples/portfolio_backtesting/backtest_outputs"

    @property
    def stable_portfolio(self) -> Path:
        return self.stable_repo / "examples/portfolio_backtesting"

    @property
    def stable_trader(self) -> Path:
        return self.stable_repo / ".vntrader"

    @property
    def qualification_evidence(self) -> Path:
        return self.state_root / "qualification-bundle/qualification.json"

    @property
    def release_manifest(self) -> Path:
        return self.state_root / "release-manifest.json"

    @property
    def activation_receipt(self) -> Path:
        return self.state_root / "runtime/state/activation_receipt.json"

    @property
    def activation_audit(self) -> Path:
        return self.state_root / "activation/latest.json"

    @property
    def activation_attempt_audit(self) -> Path:
        return self.state_root / "activation/attempt-latest.json"

    @property
    def plist_rollback_root(self) -> Path:
        return self.state_root / "activation/rollback"

    @property
    def plist_rollback_manifest(self) -> Path:
        return self.plist_rollback_root / "manifest.json"

    @property
    def plist_staging_root(self) -> Path:
        return self.state_root / "activation/staging"

    @property
    def install_lock(self) -> Path:
        return self.state_root / "activation/transaction.lock"


def canonical_install_paths() -> ProductionInstallPaths:
    return ProductionInstallPaths(
        main_repo=MAIN_REPO,
        stable_repo=STABLE_REPO,
        state_root=STATE_ROOT,
        launchd_install_dir=LAUNCHD_INSTALL_DIR,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_regular(path: Path, *, allow_public_read: bool = False) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ProductionInstallError(
            f"production_install_file_missing:{path.name}"
        ) from exc
    forbidden = 0o022 | (0 if allow_public_read else 0o077)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & forbidden
    ):
        raise ProductionInstallError(
            f"production_install_file_security_invalid:{path.name}"
        )
    return path.resolve(strict=True)


def _assert_no_symlink_components(path: Path) -> None:
    candidate = Path(os.path.abspath(path.expanduser()))
    for component in tuple(reversed(candidate.parents)) + (candidate,):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProductionInstallError(
                f"production_activation_path_lstat_failed:{path.name}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ProductionInstallError(
                f"production_activation_path_symlink_forbidden:{path.name}"
            )


def _private_directory(path: Path) -> Path:
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ProductionInstallError(
            f"production_install_directory_missing:{path.name}"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ProductionInstallError(
            f"production_install_directory_security_invalid:{path.name}"
        )
    path.chmod(0o700)
    return path.resolve(strict=True)


@contextmanager
def _exclusive_install_lock(paths: ProductionInstallPaths):
    """Serialize prepare and activation without mutating a busy generation."""

    lock_path = paths.install_lock
    _assert_no_symlink_components(lock_path.parent)
    if not lock_path.parent.exists():
        _private_directory(lock_path.parent)
    else:
        metadata = lock_path.parent.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise ProductionInstallError(
                "production_install_lock_directory_security_invalid"
            )
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise ProductionInstallError(
            "production_install_lock_open_failed"
        ) from exc
    locked = False
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise ProductionInstallError(
                "production_install_lock_security_invalid"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise ProductionInstallError(
                    "production_install_lock_busy"
                ) from exc
            raise ProductionInstallError(
                "production_install_lock_failed"
            ) from exc
        yield
    finally:
        if locked:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _copy_private_regular(
    source: Path,
    destination: Path,
    *,
    source_may_be_public_read: bool = False,
) -> None:
    resolved_source = _strict_regular(
        source,
        allow_public_read=source_may_be_public_read,
    )
    _private_directory(destination.parent)
    if destination.exists() or destination.is_symlink():
        resolved_destination = _strict_regular(destination)
        if stat.S_IMODE(destination.stat().st_mode) != 0o600:
            raise ProductionInstallError(
                f"production_install_destination_mode_invalid:{destination.name}"
            )
        if _sha256(resolved_source) != _sha256(resolved_destination):
            raise ProductionInstallError(
                f"production_install_destination_bytes_mismatch:{destination.name}"
            )
        return
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(resolved_source, os.O_RDONLY | nofollow)
    destination_fd = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
        0o600,
    )
    try:
        os.fchmod(destination_fd, 0o600)
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            offset = 0
            while offset < len(chunk):
                offset += os.write(destination_fd, chunk[offset:])
        os.fsync(destination_fd)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        os.close(destination_fd)
        os.close(source_fd)
    if _sha256(resolved_source) != _sha256(destination):
        destination.unlink(missing_ok=True)
        raise ProductionInstallError(
            f"production_install_copy_verification_failed:{destination.name}"
        )


def _write_private_json(path: Path, payload: dict[str, Any], *, error_tag: str) -> None:
    """Durably replace one owner-only JSON file without following a leaf link."""

    _private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ProductionInstallError(f"{error_tag}_temporary_exists")
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
        os.replace(temporary, path)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)


def _empty_plist_rollback_manifest() -> dict[str, Any]:
    return {
        "schema_version": PLIST_ROLLBACK_SCHEMA_VERSION,
        "status": "prepared",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "entries": {},
    }


def _load_plist_rollback_manifest(
    paths: ProductionInstallPaths,
) -> dict[str, Any]:
    path = paths.plist_rollback_manifest
    if not path.exists() and not path.is_symlink():
        return _empty_plist_rollback_manifest()
    resolved = _strict_regular(path)
    if stat.S_IMODE(resolved.stat().st_mode) != 0o600:
        raise ProductionInstallError(
            "production_install_rollback_manifest_mode_invalid"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProductionInstallError(
            "production_install_rollback_manifest_json_invalid"
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != PLIST_ROLLBACK_SCHEMA_VERSION
        or not isinstance(payload.get("entries"), dict)
    ):
        raise ProductionInstallError(
            "production_install_rollback_manifest_schema_invalid"
        )
    return payload


def _rollback_backup_relative_path(label: str, sha256: str) -> Path:
    return Path("plists") / f"{label}.{sha256}.plist"


def _set_plist_rollback_manifest_status(
    paths: ProductionInstallPaths,
    *,
    status: str,
    activation_manifest_sha256: str,
) -> None:
    if (
        not paths.plist_rollback_manifest.exists()
        and not paths.plist_rollback_manifest.is_symlink()
    ):
        return
    payload = _load_plist_rollback_manifest(paths)
    payload["status"] = status
    payload["activation_manifest_sha256"] = activation_manifest_sha256
    payload["activation_status_updated_at_utc"] = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    _write_private_json(
        paths.plist_rollback_manifest,
        payload,
        error_tag="production_activation_rollback_manifest",
    )


def _production_label_names() -> dict[str, str]:
    return {
        name.removesuffix(".plist"): name
        for name in PRODUCTION_PLIST_NAMES
    }


def _staged_plist_path(
    paths: ProductionInstallPaths,
    label: str,
) -> Path:
    try:
        name = _production_label_names()[label]
    except KeyError as exc:
        raise ProductionInstallError(
            f"production_install_staging_label_invalid:{label}"
        ) from exc
    return paths.plist_staging_root / name


def _validate_prepared_staging_manifest(
    paths: ProductionInstallPaths,
    *,
    prepared_source_commit: str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    manifest = _load_plist_rollback_manifest(paths)
    if manifest.get("status") != "prepared":
        raise ProductionInstallError(
            "production_activation_staging_manifest_not_prepared"
        )
    if manifest.get("prepared_source_commit") != prepared_source_commit:
        raise ProductionInstallError(
            "production_activation_staging_commit_mismatch"
        )
    entries = manifest.get("entries")
    expected = _production_label_names()
    if not isinstance(entries, dict) or set(entries) != set(expected):
        raise ProductionInstallError(
            "production_activation_staging_entries_mismatch"
        )
    labels: list[str] = []
    for label, name in expected.items():
        entry = entries.get(label)
        source = paths.stable_portfolio / "launchd" / name
        staged = _staged_plist_path(paths, label)
        source_resolved = _strict_regular(source, allow_public_read=True)
        staged_resolved = _strict_regular(staged)
        source_sha256 = _sha256(source_resolved)
        if (
            not isinstance(entry, dict)
            or entry.get("status") != "prepared"
            or entry.get("label") != label
            or entry.get("plist_name") != name
            or entry.get("prepared_source_commit")
            != prepared_source_commit
            or entry.get("prepared_sha256") != source_sha256
            or entry.get("staged_relative_path") != name
            or entry.get("previous_state") != "uninspected"
            or _sha256(staged_resolved) != source_sha256
            or staged_resolved.read_bytes() != source_resolved.read_bytes()
            or stat.S_IMODE(staged_resolved.stat().st_mode) != 0o600
        ):
            raise ProductionInstallError(
                f"production_activation_staging_entry_invalid:{label}"
            )
        try:
            payload = plistlib.loads(staged_resolved.read_bytes())
        except Exception as exc:
            raise ProductionInstallError(
                f"production_activation_staged_plist_invalid:{label}"
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("Label") != label
            or payload.get("Umask") != "077"
        ):
            raise ProductionInstallError(
                f"production_activation_staged_plist_semantics_invalid:{label}"
            )
        labels.append(label)
    return manifest, tuple(labels)


def _validate_settled_launchagents_generation(
    paths: ProductionInstallPaths,
    manifest: dict[str, Any],
) -> None:
    """Prove the prior transaction's final disk state before replacing it."""

    status = str(manifest.get("status", "") or "")
    if status not in {"activation_succeeded", "rollback_complete"}:
        raise ProductionInstallError(
            f"production_install_rollback_state_unsettled:{status or '<missing>'}"
        )
    production_entries = manifest.get("entries")
    conflict_entries = manifest.get("conflict_entries")
    if (
        not isinstance(production_entries, dict)
        or set(production_entries) != set(_production_label_names())
        or not isinstance(conflict_entries, dict)
        or set(conflict_entries) != set(CONFLICTING_JOB_LABELS)
    ):
        raise ProductionInstallError(
            "production_install_settled_generation_entries_invalid"
        )

    rows: list[tuple[str, dict[str, Any], bool]] = []
    rows.extend(
        (label, entry, True)
        for label, entry in production_entries.items()
        if isinstance(entry, dict)
    )
    rows.extend(
        (label, entry, False)
        for label, entry in conflict_entries.items()
        if isinstance(entry, dict)
    )
    if len(rows) != len(production_entries) + len(conflict_entries):
        raise ProductionInstallError(
            "production_install_settled_generation_entry_invalid"
        )
    for label, entry, is_production in rows:
        destination = paths.launchd_install_dir / f"{label}.plist"
        if status == "activation_succeeded":
            expected_state = "present" if is_production else "absent"
            expected_sha256 = (
                str(entry.get("prepared_sha256", "") or "")
                if is_production
                else ""
            )
            expected_mode = 0o600 if is_production else None
        else:
            expected_state = str(entry.get("previous_state", "") or "")
            expected_sha256 = str(entry.get("previous_sha256", "") or "")
            expected_mode = entry.get("previous_mode")
        present = destination.exists() or destination.is_symlink()
        if expected_state == "absent":
            if present:
                raise ProductionInstallError(
                    f"production_install_settled_disk_expected_absent:{label}"
                )
            continue
        if expected_state != "present" or not present:
            raise ProductionInstallError(
                f"production_install_settled_disk_expected_present:{label}"
            )
        resolved = _strict_regular(destination, allow_public_read=True)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or expected_mode not in _SAFE_PREVIOUS_PLIST_MODES
            or stat.S_IMODE(resolved.stat().st_mode) != expected_mode
            or _sha256(resolved) != expected_sha256
        ):
            raise ProductionInstallError(
                f"production_install_settled_disk_sha_mismatch:{label}"
            )


def _prepare_staged_production_plists(
    paths: ProductionInstallPaths,
    *,
    prepared_source_commit: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Stage exact definitions privately; never touch LaunchAgents."""

    existing_manifest: dict[str, Any] | None = None
    if (
        paths.plist_rollback_manifest.exists()
        or paths.plist_rollback_manifest.is_symlink()
    ):
        existing_manifest = _load_plist_rollback_manifest(paths)
        status = str(existing_manifest.get("status", "") or "")
        if status == "prepared":
            # Only exact idempotence is allowed while the prior generation has
            # not been activated.  A different generation could otherwise
            # lose the bytes still loaded by launchd.
            _validate_prepared_staging_manifest(
                paths,
                prepared_source_commit=prepared_source_commit,
            )
            return (
                {name: "staged_unchanged" for name in PRODUCTION_PLIST_NAMES},
                existing_manifest,
            )
        _validate_settled_launchagents_generation(paths, existing_manifest)

    _private_directory(paths.plist_staging_root)
    staging_statuses: dict[str, str] = {}
    entries: dict[str, Any] = {}
    for name in PRODUCTION_PLIST_NAMES:
        label = name.removesuffix(".plist")
        source = paths.stable_portfolio / "launchd" / name
        source_resolved = _strict_regular(source, allow_public_read=True)
        try:
            payload = plistlib.loads(source_resolved.read_bytes())
        except Exception as exc:
            raise ProductionInstallError(
                f"production_install_plist_invalid:{name}"
            ) from exc
        if (
            not isinstance(payload, dict)
            or payload.get("Label") != label
            or payload.get("Umask") != "077"
        ):
            raise ProductionInstallError(
                f"production_install_plist_invalid:{name}"
            )
        staged = _staged_plist_path(paths, label)
        staging_statuses[name] = _install_plist_atomically(
            source_resolved,
            staged,
        )
        entries[label] = {
            "status": "prepared",
            "label": label,
            "plist_name": name,
            "prepared_source_commit": prepared_source_commit,
            "prepared_sha256": _sha256(source_resolved),
            "staged_relative_path": name,
            "previous_state": "uninspected",
        }
    manifest = {
        "schema_version": PLIST_ROLLBACK_SCHEMA_VERSION,
        "status": "prepared",
        "generated_at_utc": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "prepared_source_commit": prepared_source_commit,
        "entries": entries,
    }
    # Publish the generation seal only after all seven staged files are exact.
    _write_private_json(
        paths.plist_rollback_manifest,
        manifest,
        error_tag="production_install_staging_manifest",
    )
    _validate_prepared_staging_manifest(
        paths,
        prepared_source_commit=prepared_source_commit,
    )
    return staging_statuses, manifest


def _journal_previous_installed_plists(
    paths: ProductionInstallPaths,
    *,
    staging_manifest: dict[str, Any],
    activation_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, Path]]:
    """Snapshot installed state and seal it before the first mutation."""

    journal = json.loads(json.dumps(staging_manifest))
    restore_paths: dict[str, Path] = {}
    for label, name in _production_label_names().items():
        entry = journal["entries"][label]
        destination = paths.launchd_install_dir / name
        if not destination.exists() and not destination.is_symlink():
            entry.update(
                {
                    "previous_state": "absent",
                    "previous_sha256": "",
                    "backup_relative_path": "",
                    "previous_mode": None,
                }
            )
            continue
        previous = _strict_regular(destination, allow_public_read=True)
        try:
            payload = plistlib.loads(previous.read_bytes())
        except Exception as exc:
            raise ProductionInstallError(
                f"production_activation_previous_plist_invalid:{label}"
            ) from exc
        if not isinstance(payload, dict) or payload.get("Label") != label:
            raise ProductionInstallError(
                f"production_activation_previous_plist_label_invalid:{label}"
            )
        previous_mode = stat.S_IMODE(previous.stat().st_mode)
        if previous_mode not in _SAFE_PREVIOUS_PLIST_MODES:
            raise ProductionInstallError(
                f"production_activation_previous_plist_mode_invalid:{label}"
            )
        previous_sha256 = _sha256(previous)
        backup_relative = _rollback_backup_relative_path(
            label,
            previous_sha256,
        )
        backup = paths.plist_rollback_root / backup_relative
        _copy_private_regular(
            previous,
            backup,
            source_may_be_public_read=True,
        )
        entry.update(
            {
                "previous_state": "present",
                "previous_sha256": previous_sha256,
                "backup_relative_path": str(backup_relative),
                "previous_mode": previous_mode,
            }
        )
        restore_paths[label] = backup.resolve(strict=True)
    conflict_entries: dict[str, Any] = {}
    for label in CONFLICTING_JOB_LABELS:
        destination = paths.launchd_install_dir / f"{label}.plist"
        entry: dict[str, Any] = {
            "label": label,
            "plist_name": f"{label}.plist",
        }
        if not destination.exists() and not destination.is_symlink():
            entry.update(
                {
                    "previous_state": "absent",
                    "previous_sha256": "",
                    "backup_relative_path": "",
                    "previous_mode": None,
                }
            )
            conflict_entries[label] = entry
            continue
        previous = _strict_regular(destination, allow_public_read=True)
        try:
            payload = plistlib.loads(previous.read_bytes())
        except Exception as exc:
            raise ProductionInstallError(
                f"production_activation_conflict_plist_invalid:{label}"
            ) from exc
        if not isinstance(payload, dict) or payload.get("Label") != label:
            raise ProductionInstallError(
                f"production_activation_conflict_plist_label_invalid:{label}"
            )
        previous_mode = stat.S_IMODE(previous.stat().st_mode)
        if previous_mode not in _SAFE_PREVIOUS_PLIST_MODES:
            raise ProductionInstallError(
                f"production_activation_conflict_plist_mode_invalid:{label}"
            )
        previous_sha256 = _sha256(previous)
        backup_relative = _rollback_backup_relative_path(
            label,
            previous_sha256,
        )
        backup = paths.plist_rollback_root / backup_relative
        _copy_private_regular(
            previous,
            backup,
            source_may_be_public_read=True,
        )
        entry.update(
            {
                "previous_state": "present",
                "previous_sha256": previous_sha256,
                "backup_relative_path": str(backup_relative),
                "previous_mode": previous_mode,
            }
        )
        conflict_entries[label] = entry
        restore_paths[label] = backup.resolve(strict=True)
    journal["conflict_entries"] = conflict_entries
    journal.update(
        {
            "status": "activation_in_progress",
            "activation_manifest_sha256": activation_manifest_sha256,
            "activation_started_at_utc": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )
    _write_private_json(
        paths.plist_rollback_manifest,
        journal,
        error_tag="production_activation_transaction_manifest",
    )
    return journal, restore_paths


def _validated_transaction_backup(
    paths: ProductionInstallPaths,
    *,
    label: str,
    entry: dict[str, Any],
) -> Path:
    expected_sha256 = str(entry.get("previous_sha256", "") or "")
    previous_mode = entry.get("previous_mode")
    relative = str(entry.get("backup_relative_path", "") or "")
    if (
        entry.get("previous_state") != "present"
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or previous_mode not in _SAFE_PREVIOUS_PLIST_MODES
        or relative
        != str(_rollback_backup_relative_path(label, expected_sha256))
    ):
        raise ProductionInstallError(
            f"production_activation_transaction_backup_entry_invalid:{label}"
        )
    backup = paths.plist_rollback_root / relative
    _assert_no_symlink_components(backup)
    resolved = _strict_regular(backup)
    if (
        stat.S_IMODE(resolved.stat().st_mode) != 0o600
        or _sha256(resolved) != expected_sha256
    ):
        raise ProductionInstallError(
            f"production_activation_transaction_backup_sha_invalid:{label}"
        )
    try:
        payload = plistlib.loads(resolved.read_bytes())
    except Exception as exc:
        raise ProductionInstallError(
            f"production_activation_transaction_backup_plist_invalid:{label}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("Label") != label:
        raise ProductionInstallError(
            f"production_activation_transaction_backup_label_invalid:{label}"
        )
    return resolved


def _validated_restored_destination(
    paths: ProductionInstallPaths,
    *,
    label: str,
    entry: dict[str, Any],
) -> Path:
    expected_sha256 = str(entry.get("previous_sha256", "") or "")
    expected_mode = entry.get("previous_mode")
    destination = paths.launchd_install_dir / f"{label}.plist"
    resolved = _strict_regular(destination, allow_public_read=True)
    if (
        entry.get("previous_state") != "present"
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or expected_mode not in _SAFE_PREVIOUS_PLIST_MODES
        or stat.S_IMODE(resolved.stat().st_mode) != expected_mode
        or _sha256(resolved) != expected_sha256
    ):
        raise ProductionInstallError(
            f"production_activation_restored_destination_invalid:{label}"
        )
    try:
        payload = plistlib.loads(resolved.read_bytes())
    except Exception as exc:
        raise ProductionInstallError(
            f"production_activation_restored_plist_invalid:{label}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("Label") != label:
        raise ProductionInstallError(
            f"production_activation_restored_label_invalid:{label}"
        )
    return resolved


def _journaled_launchagents_drift(
    paths: ProductionInstallPaths,
    transaction_manifest: dict[str, Any],
) -> list[str]:
    """Re-read every journaled destination immediately before mutation."""

    drift: list[str] = []
    groups = (
        transaction_manifest.get("entries", {}),
        transaction_manifest.get("conflict_entries", {}),
    )
    for entries in groups:
        if not isinstance(entries, dict):
            return ["journal_entries_invalid"]
        for label, entry in entries.items():
            if not isinstance(entry, dict):
                drift.append(f"journal_entry_invalid:{label}")
                continue
            destination = paths.launchd_install_dir / f"{label}.plist"
            present = destination.exists() or destination.is_symlink()
            previous_state = str(entry.get("previous_state", "") or "")
            if previous_state == "absent":
                if present:
                    drift.append(f"expected_absent_now_present:{label}")
                continue
            if previous_state != "present":
                drift.append(f"previous_state_invalid:{label}")
                continue
            expected_sha256 = str(entry.get("previous_sha256", "") or "")
            expected_mode = entry.get("previous_mode")
            if not present:
                drift.append(f"expected_present_now_absent:{label}")
                continue
            try:
                current = _strict_regular(
                    destination,
                    allow_public_read=True,
                )
                current_sha256 = _sha256(current)
                current_mode = stat.S_IMODE(current.stat().st_mode)
            except Exception as exc:
                drift.append(
                    f"present_state_unreadable:{label}:{type(exc).__name__}"
                )
                continue
            if (
                not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
                or expected_mode not in _SAFE_PREVIOUS_PLIST_MODES
                or current_sha256 != expected_sha256
                or current_mode != expected_mode
            ):
                drift.append(f"bytes_or_mode_changed_after_journal:{label}")
    return drift


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically move one path without ever replacing the destination."""

    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    source_raw = os.fsencode(source)
    destination_raw = os.fsencode(destination)
    if hasattr(libc, "renameatx_np"):
        result = libc.renameatx_np(
            -2,
            source_raw,
            -2,
            destination_raw,
            0x00000004,
        )
    elif hasattr(libc, "renameat2"):
        result = libc.renameat2(
            -100,
            source_raw,
            -100,
            destination_raw,
            0x00000001,
        )
    else:
        raise ProductionInstallError(
            "production_activation_noreplace_rename_unavailable"
        )
    if result != 0:
        error_number = ctypes.get_errno()
        raise ProductionInstallError(
            "production_activation_noreplace_rename_failed:"
            f"{source.name}:{error_number}"
        )


def _journal_entry_matches_destination(
    destination: Path,
    entry: dict[str, Any],
) -> bool:
    expected_sha256 = str(entry.get("previous_sha256", "") or "")
    expected_mode = entry.get("previous_mode")
    try:
        resolved = _strict_regular(destination, allow_public_read=True)
        before = resolved.stat()
        observed_sha256 = _sha256(resolved)
        after = resolved.stat()
    except Exception:
        return False
    return bool(
        re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        and expected_mode in _SAFE_PREVIOUS_PLIST_MODES
        and observed_sha256 == expected_sha256
        and stat.S_IMODE(after.st_mode) == expected_mode
        and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    )


def _quarantine_journaled_destination(
    paths: ProductionInstallPaths,
    *,
    label: str,
    entry: dict[str, Any],
    quarantine_root: Path,
    suffix: str,
) -> Path | None:
    """CAS one journaled destination into private quarantine."""

    destination = paths.launchd_install_dir / f"{label}.plist"
    previous_state = str(entry.get("previous_state", "") or "")
    if previous_state == "absent":
        if destination.exists() or destination.is_symlink():
            raise ProductionInstallError(
                f"production_activation_cas_expected_absent:{label}"
            )
        return None
    if previous_state != "present":
        raise ProductionInstallError(
            f"production_activation_cas_state_invalid:{label}"
        )
    quarantine = quarantine_root / f"{label}.{suffix}.plist"
    if quarantine.exists() or quarantine.is_symlink():
        raise ProductionInstallError(
            f"production_activation_quarantine_exists:{label}"
        )
    _rename_noreplace(destination, quarantine)
    if not _journal_entry_matches_destination(quarantine, entry):
        try:
            _rename_noreplace(quarantine, destination)
        except ProductionInstallError as restore_exc:
            raise ProductionInstallError(
                f"production_activation_cas_restore_blocked:{label}"
            ) from restore_exc
        raise ProductionInstallError(
            f"production_activation_cas_identity_mismatch:{label}"
        )
    return quarantine


def _publish_plist_expected_absent(source: Path, destination: Path) -> None:
    """Publish one sealed staged plist without replacing a concurrent file."""

    resolved_source = _strict_regular(source)
    if stat.S_IMODE(resolved_source.stat().st_mode) != 0o600:
        raise ProductionInstallError(
            f"production_activation_publish_source_mode_invalid:{destination.name}"
        )
    try:
        os.link(resolved_source, destination, follow_symlinks=False)
    except OSError as exc:
        raise ProductionInstallError(
            f"production_activation_publish_expected_absent_failed:{destination.name}"
        ) from exc
    parent_fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    if _sha256(destination) != _sha256(resolved_source):
        raise ProductionInstallError(
            f"production_activation_publish_verification_failed:{destination.name}"
        )


def _remove_installed_plist_for_rollback(path: Path) -> None:
    if path.exists() or path.is_symlink():
        metadata = path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise ProductionInstallError(
                f"production_activation_rollback_remove_invalid:{path.name}"
            )
        path.unlink()
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    if path.exists() or path.is_symlink():
        raise ProductionInstallError(
            f"production_activation_rollback_remove_failed:{path.name}"
        )


def _ensure_exact_symlink(link: Path, target: Path) -> None:
    target_resolved = target.resolve(strict=True)
    if link.is_symlink():
        if link.resolve(strict=True) != target_resolved:
            raise ProductionInstallError(
                f"production_install_symlink_target_mismatch:{link.name}"
            )
        return
    if link.exists():
        raise ProductionInstallError(
            f"production_install_symlink_leaf_occupied:{link.name}"
        )
    link.symlink_to(target_resolved, target_is_directory=True)


def _install_plist_atomically(source: Path, destination: Path) -> str:
    """Install or upgrade one launchd definition without loading the job."""

    resolved_source = _strict_regular(source, allow_public_read=True)
    _private_directory(destination.parent)
    destination_existed = destination.exists() or destination.is_symlink()
    if destination_existed:
        try:
            metadata = destination.lstat()
        except OSError as exc:
            raise ProductionInstallError(
                f"production_install_plist_destination_invalid:{destination.name}"
            ) from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise ProductionInstallError(
                f"production_install_plist_destination_invalid:{destination.name}"
            )
        if _sha256(resolved_source) == _sha256(destination):
            destination.chmod(0o600)
            return "unchanged"
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.installing"
    )
    if temporary.exists() or temporary.is_symlink():
        raise ProductionInstallError(
            f"production_install_plist_temporary_exists:{destination.name}"
        )
    try:
        _copy_private_regular(
            resolved_source,
            temporary,
            source_may_be_public_read=True,
        )
        os.replace(temporary, destination)
        parent_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return "updated" if destination_existed else "installed"


def _restore_installed_plist_atomically(
    source_backup: Path,
    destination: Path,
    *,
    destination_mode: int,
) -> str:
    """Restore pre-upgrade launchd bytes durably for reboot consistency."""

    resolved_backup = _strict_regular(source_backup)
    if destination_mode not in _SAFE_PREVIOUS_PLIST_MODES:
        raise ProductionInstallError(
            f"production_activation_rollback_mode_invalid:{destination.name}"
        )
    expected_sha256 = _sha256(resolved_backup)
    status = _install_plist_atomically(resolved_backup, destination)
    descriptor = os.open(
        destination,
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fchmod(descriptor, destination_mode)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    resolved_destination = _strict_regular(
        destination,
        allow_public_read=True,
    )
    if (
        stat.S_IMODE(resolved_destination.stat().st_mode) != destination_mode
        or _sha256(resolved_destination) != expected_sha256
        or resolved_destination.read_bytes() != resolved_backup.read_bytes()
    ):
        raise ProductionInstallError(
            f"production_activation_rollback_disk_restore_invalid:{destination.name}"
        )
    return status


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ProductionInstallError(
            f"production_install_git_failed:{' '.join(args)}"
        )
    return result.stdout.strip()


def _production_labels_from_plists(paths: ProductionInstallPaths) -> tuple[str, ...]:
    head = _git(paths.stable_repo, "rev-parse", "--verify", "HEAD^{commit}")
    _, labels = _validate_prepared_staging_manifest(
        paths,
        prepared_source_commit=head,
    )
    return labels


def _validate_prepared_production_chain(
    paths: ProductionInstallPaths,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    for path in (
        paths.stable_repo,
        paths.state_root,
        paths.qualification_evidence,
        paths.release_manifest,
        paths.activation_receipt,
        paths.launchd_install_dir,
    ):
        _assert_no_symlink_components(path)
    if _git(paths.stable_repo, "status", "--porcelain", "--untracked-files=all"):
        raise ProductionInstallError("production_activation_stable_tree_not_clean")
    head = _git(paths.stable_repo, "rev-parse", "--verify", "HEAD^{commit}")
    if not _COMMIT_RE.fullmatch(head):
        raise ProductionInstallError("production_activation_stable_head_invalid")
    for artifact in (
        paths.qualification_evidence,
        paths.release_manifest,
        paths.activation_receipt,
    ):
        resolved = _strict_regular(artifact)
        if stat.S_IMODE(resolved.stat().st_mode) != 0o600:
            raise ProductionInstallError(
                f"production_activation_artifact_mode_invalid:{artifact.name}"
            )
    try:
        manifest = load_and_validate_release_manifest(
            paths.release_manifest,
            repo_root=paths.stable_repo,
            expected_official_version=C9_15W_PROFILE.official_version,
            expected_capital=C9_15W_PROFILE.capital,
            expected_capital_label=C9_15W_PROFILE.capital_label,
            expected_execution_profile=C9_15W_PROFILE.profile_key,
            required_runtime_profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
            current_commit=head,
        )
        evidence = load_and_validate_production_qualification_evidence(
            paths.qualification_evidence,
            repo_root=paths.stable_repo,
            source_commit=head,
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=[
                str(item.get("path", ""))
                for item in manifest.get("critical_files", [])
                if isinstance(item, dict)
            ],
            manifest_created_at_utc=str(manifest.get("created_at_utc", "")),
        )
    except (ReleaseManifestError, OSError, ValueError) as exc:
        raise ProductionInstallError(
            "production_activation_release_or_qualification_invalid"
        ) from exc
    qualification = manifest.get("strategy_semantics_qualification")
    if (
        not isinstance(qualification, dict)
        or qualification.get("status") != "passed"
        or qualification.get("evidence_id") != evidence.get("evidence_sha256")
    ):
        raise ProductionInstallError(
            "production_activation_qualification_binding_invalid"
        )
    receipt_blockers = validate_stage179_activation_receipt(
        paths.activation_receipt,
        manifest_sha256=str(manifest.get("manifest_sha256", "")),
        official_version=C9_15W_PROFILE.official_version,
        capital=C9_15W_PROFILE.capital,
        capital_label=C9_15W_PROFILE.capital_label,
    )
    if receipt_blockers:
        raise ProductionInstallError(
            "production_activation_receipt_invalid:"
            + ",".join(receipt_blockers)
        )
    labels = _production_labels_from_plists(paths)
    return manifest, labels


def _launchctl_call(
    runner: Any,
    *arguments: str,
) -> tuple[dict[str, Any], str]:
    command = ["/bin/launchctl", *arguments]
    try:
        result = runner(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return (
            {
                "arguments": list(arguments),
                "exit_code": -1,
                "exception_type": type(exc).__name__,
            },
            "",
        )
    return (
        {
            "arguments": list(arguments),
            "exit_code": int(result.returncode),
        },
        str(result.stdout or ""),
    )


def _parse_launchctl_state(output: str) -> tuple[str, int | None]:
    state = ""
    pid: int | None = None
    for line in output.splitlines():
        text = line.strip()
        if text.startswith("state = "):
            state = text.split("=", 1)[1].strip()
        elif text.startswith("pid = "):
            try:
                pid = int(text.split("=", 1)[1].strip())
            except ValueError:
                pid = None
    return state, pid


def _is_owned_launchd_label(value: str) -> bool:
    return bool(
        value.startswith(OWNED_LAUNCHD_LABEL_PREFIXES)
        and _OWNED_LABEL_RE.fullmatch(value)
    )


def _discover_owned_launchagents_disk(
    launchd_install_dir: Path,
) -> dict[str, Any]:
    labels: set[str] = set()
    blockers: list[str] = []
    label_sources: dict[str, str] = {}
    fingerprints: dict[str, dict[str, Any]] = {}
    directory_fd = -1
    try:
        directory_fd = os.open(
            launchd_install_dir,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except FileNotFoundError:
        return {
            "labels": [],
            "blockers": [],
            "scanned_plist_count": 0,
            "scanned_plist_names": [],
            "fingerprints": {},
        }
    except OSError as exc:
        return {
            "labels": [],
            "blockers": [
                "launchagents_directory_unreadable:"
                f"{type(exc).__name__}"
            ],
            "scanned_plist_count": 0,
            "scanned_plist_names": [],
            "fingerprints": {},
        }
    directory_metadata = os.fstat(directory_fd)
    if (
        not stat.S_ISDIR(directory_metadata.st_mode)
        or directory_metadata.st_uid != os.getuid()
        or stat.S_IMODE(directory_metadata.st_mode) & 0o022
    ):
        os.close(directory_fd)
        return {
            "labels": [],
            "blockers": ["launchagents_directory_security_invalid"],
            "scanned_plist_count": 0,
            "scanned_plist_names": [],
            "fingerprints": {},
        }

    try:
        with os.scandir(directory_fd) as iterator:
            entries = sorted(iterator, key=lambda item: item.name)
    except OSError as exc:
        os.close(directory_fd)
        return {
            "labels": [],
            "blockers": [f"launchagents_scandir_failed:{type(exc).__name__}"],
            "scanned_plist_count": 0,
            "scanned_plist_names": [],
            "fingerprints": {},
        }

    scanned_plist_count = 0
    scanned_plist_names: list[str] = []
    for entry in entries:
        name = entry.name
        if not name.endswith(".plist"):
            if name.startswith(OWNED_LAUNCHD_LABEL_PREFIXES):
                blockers.append(f"owned_launchagent_non_plist:{name}")
            continue
        scanned_plist_count += 1
        scanned_plist_names.append(name)
        filename_label = name.removesuffix(".plist")
        filename_has_owned_prefix = filename_label.startswith(
            OWNED_LAUNCHD_LABEL_PREFIXES
        )
        filename_owned = _is_owned_launchd_label(filename_label)
        if filename_has_owned_prefix and not filename_owned:
            blockers.append(f"owned_launchagent_filename_invalid:{name}")
        try:
            initial = entry.stat(follow_symlinks=False)
        except OSError as exc:
            blockers.append(
                f"launchagent_lstat_failed:{name}:{type(exc).__name__}"
            )
            continue
        if stat.S_ISLNK(initial.st_mode) or not stat.S_ISREG(initial.st_mode):
            blockers.append(f"launchagent_not_regular_no_follow:{name}")
            if filename_owned:
                labels.add(filename_label)
            continue
        descriptor = -1
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_fd,
            )
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino)
                != (initial.st_dev, initial.st_ino)
            ):
                raise ProductionInstallError(
                    "launchagent_changed_during_open"
                )
            opened_mode = stat.S_IMODE(opened.st_mode)
            if (
                opened.st_uid != os.getuid()
                or opened_mode not in _SAFE_PREVIOUS_PLIST_MODES
            ):
                blockers.append(f"launchagent_security_invalid:{name}")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 1024 * 1024:
                    raise ProductionInstallError("launchagent_oversized")
                chunks.append(chunk)
            raw = b"".join(chunks)
            opened_after = os.fstat(descriptor)
            if (
                (opened_after.st_dev, opened_after.st_ino)
                != (opened.st_dev, opened.st_ino)
                or opened_after.st_size != opened.st_size
                or opened_after.st_mtime_ns != opened.st_mtime_ns
                or opened_after.st_ctime_ns != opened.st_ctime_ns
                or stat.S_IMODE(opened_after.st_mode)
                != stat.S_IMODE(opened.st_mode)
            ):
                raise ProductionInstallError(
                    "launchagent_changed_during_read"
                )
            payload = plistlib.loads(raw)
            if not isinstance(payload, dict):
                raise ProductionInstallError("launchagent_not_dictionary")
        except Exception as exc:
            blockers.append(
                f"launchagent_uninspectable:{name}:{type(exc).__name__}"
            )
            if filename_owned:
                labels.add(filename_label)
            continue
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        payload_label = payload.get("Label")
        payload_has_owned_prefix = isinstance(payload_label, str) and (
            payload_label.startswith(OWNED_LAUNCHD_LABEL_PREFIXES)
        )
        payload_owned = isinstance(payload_label, str) and (
            _is_owned_launchd_label(payload_label)
        )
        if payload_has_owned_prefix and not payload_owned:
            blockers.append(f"owned_launchagent_payload_label_invalid:{name}")
        if not (filename_owned or payload_owned):
            continue
        if filename_owned:
            labels.add(filename_label)
        if payload_owned:
            labels.add(payload_label)
        mode = stat.S_IMODE(opened.st_mode)
        if not (
            filename_owned
            and payload_owned
            and payload_label == filename_label
        ):
            blockers.append(f"owned_launchagent_filename_label_mismatch:{name}")
        if payload_owned:
            previous_source = label_sources.get(payload_label)
            if previous_source is not None and previous_source != name:
                blockers.append(
                    f"owned_launchagent_duplicate_label:{payload_label}"
                )
            label_sources[payload_label] = name
        for owned_label in {filename_label, payload_label}:
            if isinstance(owned_label, str) and _is_owned_launchd_label(
                owned_label
            ):
                fingerprints[owned_label] = {
                    "filename": name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "mode": mode,
                    "device": opened.st_dev,
                    "inode": opened.st_ino,
                    "size": opened.st_size,
                    "mtime_ns": opened.st_mtime_ns,
                }
    directory_after = os.fstat(directory_fd)
    if (
        (directory_after.st_dev, directory_after.st_ino)
        != (directory_metadata.st_dev, directory_metadata.st_ino)
        or directory_after.st_mtime_ns != directory_metadata.st_mtime_ns
        or directory_after.st_ctime_ns != directory_metadata.st_ctime_ns
    ):
        blockers.append("launchagents_directory_changed_during_scan")
    os.close(directory_fd)
    return {
        "labels": sorted(labels),
        "blockers": sorted(set(blockers)),
        "scanned_plist_count": scanned_plist_count,
        "scanned_plist_names": scanned_plist_names,
        "fingerprints": fingerprints,
    }


def _launchctl_output_has_complete_root(
    output: str,
    *,
    expected_header: str,
    require_services: bool,
) -> bool:
    lines = [line.rstrip() for line in output.splitlines() if line.strip()]
    if (
        not lines
        or not re.fullmatch(
            rf"\s*{re.escape(expected_header)}\s*=\s*\{{\s*",
            lines[0],
        )
        or lines[-1].strip() != "}"
        or (
            require_services
            and not any(
                re.fullmatch(r"\s*services\s*=\s*\{\s*", line)
                for line in lines
            )
        )
    ):
        return False
    depth = 0
    quote = ""
    escaped = False
    for character in output:
        if escaped:
            escaped = False
            continue
        if quote:
            if character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {"\"", "'"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quote


def _parse_owned_labels_from_launchctl_domain(
    output: str,
    *,
    uid_domain: str,
) -> tuple[set[str], list[str]]:
    labels: set[str] = set()
    blockers: list[str] = []
    if not _launchctl_output_has_complete_root(
        output,
        expected_header=uid_domain,
        require_services=True,
    ):
        return set(), ["launchctl_domain_output_header_invalid"]
    lines = output.splitlines()
    service_open_indexes = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"\s*services\s*=\s*\{\s*", line)
    ]
    if len(service_open_indexes) != 1:
        return set(), ["launchctl_domain_services_block_invalid"]
    service_open_index = service_open_indexes[0]
    service_indent = len(lines[service_open_index]) - len(
        lines[service_open_index].lstrip()
    )
    service_close_index: int | None = None
    for index in range(service_open_index + 1, len(lines)):
        line = lines[index]
        indent = len(line) - len(line.lstrip())
        if indent == service_indent and line.strip() == "}":
            service_close_index = index
            break
    if service_close_index is None:
        return set(), ["launchctl_domain_services_block_truncated"]

    service_labels: set[str] = set()
    for line in lines[service_open_index + 1 : service_close_index]:
        if not any(prefix in line for prefix in OWNED_LAUNCHD_LABEL_PREFIXES):
            continue
        match = re.fullmatch(
            r"\s*(-?\d+)\s+(-|-?\d+|\([A-Za-z]+\))\s+"
            r"(local\.qmt-roll\.(?:official-live|stage179)\."
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,199})\s*",
            line,
        )
        if match is None or not _is_owned_launchd_label(match.group(3)):
            blockers.append("launchctl_domain_owned_service_row_invalid")
            continue
        service_labels.add(match.group(3))

    lexical_labels: set[str] = set()
    for prefix in OWNED_LAUNCHD_LABEL_PREFIXES:
        offset = 0
        while True:
            start = output.find(prefix, offset)
            if start < 0:
                break
            match = _OWNED_LABEL_RE.match(output, start)
            if match is None:
                blockers.append(
                    f"launchctl_domain_owned_token_invalid:{prefix}"
                )
                offset = start + len(prefix)
                continue
            label = match.group(0)
            following = output[match.end() : match.end() + 1]
            preceding = output[start - 1 : start] if start else ""
            if (
                (preceding and preceding in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
                or (
                    following
                    and following
                    not in " \t\r\n=;{},()[]<>\"'"
                )
            ):
                blockers.append(
                    f"launchctl_domain_owned_token_boundary_invalid:{label}"
                )
            else:
                lexical_labels.add(label)
            offset = max(match.end(), start + len(prefix))
    if lexical_labels != service_labels:
        blockers.append("launchctl_domain_owned_lexical_services_mismatch")
    labels.update(service_labels)
    return labels, sorted(set(blockers))


def inspect_owned_launchd_surface(
    *,
    launchd_install_dir: Path,
    allowed_production_labels: tuple[str, ...],
    known_conflicting_labels: tuple[str, ...],
    launchctl_runner: Any = subprocess.run,
    uid: int | None = None,
) -> dict[str, Any]:
    """Read the complete owned LaunchAgents/launchd surface without mutation."""

    expected = set(allowed_production_labels)
    known_conflicts = set(known_conflicting_labels)
    if (
        len(expected) != len(allowed_production_labels)
        or not all(_is_owned_launchd_label(label) for label in expected)
        or not all(_is_owned_launchd_label(label) for label in known_conflicts)
    ):
        raise ProductionInstallError(
            "production_launchd_surface_expected_labels_invalid"
        )
    disk = _discover_owned_launchagents_disk(launchd_install_dir)
    blockers = list(disk["blockers"])
    disk_labels = set(disk["labels"])
    effective_uid = os.getuid() if uid is None else uid
    uid_domain = f"gui/{effective_uid}"
    domain_step, domain_output = _launchctl_call(
        launchctl_runner,
        "print",
        uid_domain,
    )
    steps: list[dict[str, Any]] = [
        {"phase": "owned_surface_domain", **domain_step}
    ]
    launchctl_called_count = 1
    domain_labels: set[str] = set()
    if domain_step["exit_code"] != 0:
        blockers.append(
            "launchctl_domain_unavailable:"
            f"{domain_step['exit_code']}"
        )
    else:
        domain_labels, parse_blockers = (
            _parse_owned_labels_from_launchctl_domain(
                domain_output,
                uid_domain=uid_domain,
            )
        )
        blockers.extend(parse_blockers)

    loaded_labels: set[str] = set()
    jobs: dict[str, dict[str, Any]] = {}
    candidates = sorted(
        expected | known_conflicts | disk_labels | domain_labels
    )
    if domain_step["exit_code"] == 0 and not any(
        blocker.startswith("launchctl_domain_output_header_invalid")
        for blocker in blockers
    ):
        for label in candidates:
            step, output = _launchctl_call(
                launchctl_runner,
                "print",
                f"{uid_domain}/{label}",
            )
            launchctl_called_count += 1
            state, pid = _parse_launchctl_state(output)
            if step["exit_code"] == 0:
                if _launchctl_output_has_complete_root(
                    output,
                    expected_header=f"{uid_domain}/{label}",
                    require_services=False,
                ):
                    loaded = True
                    loaded_labels.add(label)
                else:
                    loaded = None
                    blockers.append(
                        f"launchctl_owned_job_output_invalid:{label}"
                    )
            elif step["exit_code"] == 113:
                if (
                    "could not find service" in output.lower()
                    and label in output
                ):
                    loaded = False
                else:
                    loaded = None
                    blockers.append(
                        f"launchctl_owned_job_not_found_unverified:{label}"
                    )
            else:
                loaded = None
                blockers.append(
                    f"launchctl_owned_job_state_unknown:{label}:"
                    f"{step['exit_code']}"
                )
            if label in domain_labels and loaded is not True:
                blockers.append(
                    f"launchctl_domain_token_not_confirmed:{label}"
                )
            row = {
                "label": label,
                "loaded": loaded,
                "state": state,
                "pid": pid,
                **step,
            }
            jobs[label] = row
            steps.append({"phase": "owned_surface_job", **row})

    domain_second_step, domain_second_output = _launchctl_call(
        launchctl_runner,
        "print",
        uid_domain,
    )
    launchctl_called_count += 1
    steps.append(
        {"phase": "owned_surface_domain_revalidation", **domain_second_step}
    )
    domain_second_labels: set[str] = set()
    if domain_second_step["exit_code"] != 0:
        blockers.append(
            "launchctl_domain_revalidation_unavailable:"
            f"{domain_second_step['exit_code']}"
        )
    else:
        domain_second_labels, second_parse_blockers = (
            _parse_owned_labels_from_launchctl_domain(
                domain_second_output,
                uid_domain=uid_domain,
            )
        )
        blockers.extend(second_parse_blockers)
    if domain_second_labels != domain_labels:
        blockers.append("launchctl_owned_domain_changed_during_scan")
    domain_labels |= domain_second_labels

    disk_second = _discover_owned_launchagents_disk(launchd_install_dir)
    blockers.extend(disk_second["blockers"])
    if (
        disk_second["labels"] != disk["labels"]
        or disk_second["scanned_plist_names"]
        != disk["scanned_plist_names"]
        or disk_second["fingerprints"] != disk["fingerprints"]
    ):
        blockers.append("owned_launchagents_disk_changed_during_scan")
    disk_labels |= set(disk_second["labels"])

    unknown_disk = disk_labels - expected - known_conflicts
    unknown_domain = domain_labels - expected - known_conflicts
    unknown_loaded = loaded_labels - expected - known_conflicts
    unknown_owned = unknown_disk | unknown_domain | unknown_loaded
    blockers.extend(
        f"unknown_owned_launchd_label:{label}"
        for label in sorted(unknown_owned)
    )
    return {
        "status": "verified" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "disk_owned_labels": sorted(disk_labels),
        "domain_owned_labels": sorted(domain_labels),
        "loaded_owned_labels": sorted(loaded_labels),
        "unknown_disk_owned_labels": sorted(unknown_disk),
        "unknown_domain_owned_labels": sorted(unknown_domain),
        "unknown_loaded_owned_labels": sorted(unknown_loaded),
        "unknown_owned_labels": sorted(unknown_owned),
        "known_conflicting_loaded_labels": sorted(
            loaded_labels & known_conflicts
        ),
        "production_loaded_labels": sorted(loaded_labels & expected),
        "production_disk_labels": sorted(disk_labels & expected),
        "scanned_plist_count": disk["scanned_plist_count"],
        "launchctl_called_count": launchctl_called_count,
        "steps": steps,
        "jobs": jobs,
    }


def validate_exact_owned_launchd_surface(
    *,
    launchd_install_dir: Path,
    allowed_production_labels: tuple[str, ...],
    known_conflicting_labels: tuple[str, ...],
    launchctl_runner: Any = subprocess.run,
    uid: int | None = None,
) -> dict[str, Any]:
    report = inspect_owned_launchd_surface(
        launchd_install_dir=launchd_install_dir,
        allowed_production_labels=allowed_production_labels,
        known_conflicting_labels=known_conflicting_labels,
        launchctl_runner=launchctl_runner,
        uid=uid,
    )
    blockers = list(report["blockers"])
    expected = set(allowed_production_labels)
    disk = set(report["disk_owned_labels"])
    domain = set(report["domain_owned_labels"])
    loaded = set(report["loaded_owned_labels"])
    if disk != expected:
        blockers.append("owned_launchagents_disk_not_exact_production_set")
    if loaded != expected:
        blockers.append("owned_launchd_loaded_not_exact_production_set")
    if domain != expected:
        blockers.append("owned_launchd_domain_not_exact_production_set")
    return {
        **report,
        "status": "verified_exact" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "disk_exact_production": disk == expected,
        "domain_exact_production": domain == expected,
        "loaded_exact_production": loaded == expected,
    }


# The production installer and both runtime readers use the exact same
# stdlib-only discovery implementation.  The local definitions above remain
# temporarily source-compatible for older imports but are not on the call path.
inspect_owned_launchd_surface = shared_inspect_owned_launchd_surface
validate_exact_owned_launchd_surface = (
    shared_validate_exact_owned_launchd_surface
)


def _write_activation_audit(
    paths: ProductionInstallPaths,
    audit: dict[str, Any],
) -> None:
    _write_private_json(
        paths.activation_audit,
        audit,
        error_tag="production_activation_audit",
    )


def _write_activation_attempt_audit(
    paths: ProductionInstallPaths,
    audit: dict[str, Any],
) -> None:
    _write_private_json(
        paths.activation_attempt_audit,
        audit,
        error_tag="production_activation_attempt_audit",
    )


def activate_prepared_production(
    paths: ProductionInstallPaths,
    *,
    confirmation: str,
    launchctl_runner: Any = subprocess.run,
    _lock_held: bool = False,
) -> dict[str, Any]:
    if not _lock_held:
        with _exclusive_install_lock(paths):
            return activate_prepared_production(
                paths,
                confirmation=confirmation,
                launchctl_runner=launchctl_runner,
                _lock_held=True,
            )
    if confirmation != PRODUCTION_ACTIVATION_CONFIRM_TEXT:
        raise ProductionInstallError(
            "production_activation_confirmation_missing"
        )
    manifest, production_labels = _validate_prepared_production_chain(paths)
    prepared_source_commit = _git(
        paths.stable_repo, "rev-parse", "--verify", "HEAD^{commit}"
    )
    staging_manifest, staged_labels = _validate_prepared_staging_manifest(
        paths,
        prepared_source_commit=prepared_source_commit,
    )
    if tuple(production_labels) != tuple(staged_labels):
        raise ProductionInstallError(
            "production_activation_release_staging_labels_mismatch"
        )
    uid_domain = f"gui/{os.getuid()}"
    audit: dict[str, Any] = {
        "model_tag": "stage948_production_activation_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "status": "activation_preflight_complete",
        "source_commit": str(manifest.get("source_commit", "")),
        "manifest_sha256": str(manifest.get("manifest_sha256", "")),
        "steps": [],
        "production_labels": list(production_labels),
        "previously_loaded_labels": [],
        "bootstrapped_labels": [],
        "restored_labels": [],
        "rollback_results": [],
        "rollback_invocation_count": 0,
        "rollback_failure_count": 0,
        "rollback_complete": None,
        "post_activation_session_kickstart_required": True,
        "post_activation_session_kickstart_labels": [
            "local.qmt-roll.official-live.15w.c9-production-live-day-session",
            "local.qmt-roll.official-live.15w.c9-production-live-night-session",
        ],
        "launchctl_called_count": 0,
        "ctp_connection_attempted_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
    }

    target_labels = tuple(
        dict.fromkeys((*CONFLICTING_JOB_LABELS, *production_labels))
    )
    preflight_surface = inspect_owned_launchd_surface(
        launchd_install_dir=paths.launchd_install_dir,
        allowed_production_labels=production_labels,
        known_conflicting_labels=CONFLICTING_JOB_LABELS,
        launchctl_runner=launchctl_runner,
    )
    audit["steps"].extend(preflight_surface["steps"])
    audit["launchctl_called_count"] += preflight_surface[
        "launchctl_called_count"
    ]
    audit["preflight_owned_surface"] = {
        key: preflight_surface[key]
        for key in (
            "status",
            "blockers",
            "disk_owned_labels",
            "domain_owned_labels",
            "loaded_owned_labels",
            "unknown_owned_labels",
        )
    }
    if preflight_surface["status"] != "verified":
        audit["status"] = "activation_blocked_owned_surface"
        _write_activation_attempt_audit(paths, audit)
        raise ProductionActivationError(
            "production_activation_owned_surface_unverified:"
            + ",".join(preflight_surface["blockers"]),
            audit=audit,
        )

    previously_loaded: list[str] = []
    for label in target_labels:
        job = preflight_surface["jobs"].get(label)
        if not isinstance(job, dict) or job.get("loaded") not in {True, False}:
            audit["status"] = "activation_blocked_job_state_unknown"
            _write_activation_attempt_audit(paths, audit)
            raise ProductionActivationError(
                f"production_activation_job_state_unknown:{label}",
                audit=audit,
            )
        loaded = bool(job["loaded"])
        state = str(job.get("state", "") or "")
        pid = job.get("pid")
        if not loaded:
            continue
        if state.lower() == "running" or (type(pid) is int and pid > 0):
            audit["status"] = "activation_blocked_running_job"
            _write_activation_attempt_audit(paths, audit)
            raise ProductionActivationError(
                f"production_activation_running_job:{label}",
                audit=audit,
            )
        restore_path = paths.launchd_install_dir / f"{label}.plist"
        try:
            resolved_restore = _strict_regular(
                restore_path,
                allow_public_read=True,
            )
            payload = plistlib.loads(resolved_restore.read_bytes())
        except Exception as exc:
            audit["status"] = "activation_blocked_restore_plan_invalid"
            _write_activation_attempt_audit(paths, audit)
            raise ProductionActivationError(
                f"production_activation_loaded_job_not_restorable:{label}",
                audit=audit,
            ) from exc
        if not isinstance(payload, dict) or payload.get("Label") != label:
            audit["status"] = "activation_blocked_restore_plan_invalid"
            _write_activation_attempt_audit(paths, audit)
            raise ProductionActivationError(
                f"production_activation_restore_plist_label_invalid:{label}",
                audit=audit,
            )
        previously_loaded.append(label)
        audit["previously_loaded_labels"].append(label)

    transaction_manifest, journal_restore_paths = (
        _journal_previous_installed_plists(
            paths,
            staging_manifest=staging_manifest,
            activation_manifest_sha256=str(
                manifest.get("manifest_sha256", "")
            ),
        )
    )
    transaction_entries = {
        **transaction_manifest.get("entries", {}),
        **transaction_manifest.get("conflict_entries", {}),
    }

    def record_pre_mutation_block(reason: str) -> None:
        audit.update(
            {
                "status": "activation_blocked_pre_mutation",
                "failure_reason": reason,
                "manual_recovery_required": True,
            }
        )
        try:
            _set_plist_rollback_manifest_status(
                paths,
                status="rollback_incomplete",
                activation_manifest_sha256=str(
                    manifest.get("manifest_sha256", "")
                ),
            )
        except ProductionInstallError as exc:
            audit["pre_mutation_manifest_status_error"] = type(exc).__name__
        _write_activation_attempt_audit(paths, audit)

    for label in previously_loaded:
        entry = transaction_entries.get(label)
        try:
            if (
                not isinstance(entry, dict)
                or label not in journal_restore_paths
                or _validated_transaction_backup(
                    paths,
                    label=label,
                    entry=entry,
                )
                != journal_restore_paths[label]
            ):
                raise ProductionInstallError(
                    "production_activation_loaded_backup_mismatch"
                )
        except ProductionInstallError as exc:
            record_pre_mutation_block(
                f"loaded_job_backup_unverifiable:{label}"
            )
            raise ProductionActivationError(
                f"production_activation_loaded_job_not_restorable:{label}",
                audit=audit,
            ) from exc

    pre_mutation_surface = inspect_owned_launchd_surface(
        launchd_install_dir=paths.launchd_install_dir,
        allowed_production_labels=production_labels,
        known_conflicting_labels=CONFLICTING_JOB_LABELS,
        launchctl_runner=launchctl_runner,
    )
    audit["steps"].extend(pre_mutation_surface["steps"])
    audit["launchctl_called_count"] += pre_mutation_surface[
        "launchctl_called_count"
    ]
    surface_identity_fields = (
        "disk_owned_labels",
        "domain_owned_labels",
        "loaded_owned_labels",
        "disk_fingerprints",
    )
    surface_changed = any(
        pre_mutation_surface.get(field_name)
        != preflight_surface.get(field_name)
        for field_name in surface_identity_fields
    )
    now_running = [
        label
        for label in target_labels
        if isinstance(pre_mutation_surface["jobs"].get(label), dict)
        and (
            str(
                pre_mutation_surface["jobs"][label].get("state", "")
            ).lower()
            == "running"
            or (
                type(pre_mutation_surface["jobs"][label].get("pid")) is int
                and pre_mutation_surface["jobs"][label]["pid"] > 0
            )
        )
    ]
    if (
        pre_mutation_surface["status"] != "verified"
        or surface_changed
        or now_running
    ):
        audit["pre_mutation_owned_surface"] = {
            "status": pre_mutation_surface["status"],
            "blockers": pre_mutation_surface["blockers"],
            "unknown_owned_labels": pre_mutation_surface[
                "unknown_owned_labels"
            ],
            "surface_changed": surface_changed,
            "running_labels": now_running,
        }
        record_pre_mutation_block("owned_surface_changed_after_preflight")
        raise ProductionActivationError(
            "production_activation_owned_surface_changed_before_mutation",
            audit=audit,
        )

    journal_drift = _journaled_launchagents_drift(
        paths,
        transaction_manifest,
    )
    if journal_drift:
        audit["rollback_failures"] = journal_drift
        audit["steps"].append(
            {
                "phase": "pre_mutation_journal_revalidation",
                "exit_code": -1,
                "drift": journal_drift,
            }
        )
        record_pre_mutation_block("launchagents_changed_after_journal")
        raise ProductionActivationError(
            "production_activation_launchagents_changed_after_journal",
            audit=audit,
        )

    audit["steps"].append(
        {
            "phase": "pre_mutation_journal_revalidation",
            "exit_code": 0,
        }
    )

    # Publish in-progress only after every read-only preflight and journal
    # revalidation has passed, immediately before the first live mutation.
    audit["status"] = "activation_in_progress"
    _write_activation_audit(paths, audit)
    _private_directory(paths.launchd_install_dir)
    quarantine_root = _private_directory(
        paths.plist_rollback_root
        / "quarantine"
        / str(manifest.get("manifest_sha256", ""))
    )
    quarantined_originals: dict[str, Path] = {}
    published_production: set[str] = set()
    rollback_called = False

    def rollback(reason: str) -> None:
        nonlocal rollback_called
        if rollback_called:
            return
        rollback_called = True
        audit["rollback_invocation_count"] = 1
        audit["status"] = "activation_failed_rollback_attempted"
        audit["failure_reason"] = reason
        rollback_failures: list[str] = []
        cleanup_labels = list(target_labels)
        for label in reversed(cleanup_labels):
            step, _ = _launchctl_call(
                launchctl_runner,
                "bootout",
                f"{uid_domain}/{label}",
            )
            audit["launchctl_called_count"] += 1
            audit["steps"].append(
                {"phase": "rollback_ensure_absent", "label": label, **step}
            )
            verify, verify_output = _launchctl_call(
                launchctl_runner,
                "print",
                f"{uid_domain}/{label}",
            )
            audit["launchctl_called_count"] += 1
            audit["steps"].append(
                {
                    "phase": "rollback_verify_absent",
                    "label": label,
                    **verify,
                }
            )
            loaded_state, _state, _pid, _classification = (
                classify_individual_launchctl_result(
                    exit_code=verify["exit_code"],
                    output=verify_output,
                    label=label,
                    uid=os.getuid(),
                )
            )
            absent_confirmed = loaded_state is False
            result = {
                "operation": "ensure_job_absent",
                "label": label,
                "bootout_exit_code": step["exit_code"],
                "verify_exit_code": verify["exit_code"],
                "absent_confirmed": absent_confirmed,
            }
            audit["rollback_results"].append(result)
            if not absent_confirmed:
                rollback_failures.append(
                    "rollback_job_absence_unconfirmed:"
                    f"{label}:bootout={step['exit_code']};"
                    f"verify={verify['exit_code']}"
                )

        disk_entries: list[tuple[str, dict[str, Any], bool]] = []
        disk_entries.extend(
            (label, entry, True)
            for label, entry in transaction_manifest.get(
                "entries", {}
            ).items()
        )
        disk_entries.extend(
            (label, entry, False)
            for label, entry in transaction_manifest.get(
                "conflict_entries", {}
            ).items()
        )
        for label, entry, is_production in disk_entries:
            destination = paths.launchd_install_dir / f"{label}.plist"
            previous_state = str(entry.get("previous_state", "") or "")
            restore_sha256 = str(entry.get("previous_sha256", "") or "")
            try:
                if label in published_production:
                    prepared_entry = {
                        "previous_state": "present",
                        "previous_sha256": str(
                            transaction_manifest["entries"][label].get(
                                "prepared_sha256", ""
                            )
                        ),
                        "previous_mode": 0o600,
                    }
                    _quarantine_journaled_destination(
                        paths,
                        label=label,
                        entry=prepared_entry,
                        quarantine_root=quarantine_root,
                        suffix="rollback-published",
                    )
                if previous_state == "present":
                    _validated_transaction_backup(
                        paths,
                        label=label,
                        entry=entry,
                    )
                    if destination.exists() or destination.is_symlink():
                        if not _journal_entry_matches_destination(
                            destination, entry
                        ):
                            raise ProductionInstallError(
                                "production_activation_rollback_destination_occupied"
                            )
                        disk_restore_status = "previous_bytes_already_present"
                    else:
                        original = quarantined_originals.get(label)
                        if original is None:
                            raise ProductionInstallError(
                                "production_activation_rollback_quarantine_missing"
                            )
                        if not _journal_entry_matches_destination(
                            original, entry
                        ):
                            raise ProductionInstallError(
                                "production_activation_rollback_quarantine_invalid"
                            )
                        _rename_noreplace(original, destination)
                        if not _journal_entry_matches_destination(
                            destination, entry
                        ):
                            raise ProductionInstallError(
                                "production_activation_rollback_restore_invalid"
                            )
                        disk_restore_status = "restored_from_quarantine"
                    operation = "restore_previous_without_overwrite"
                elif previous_state == "absent":
                    if destination.exists() or destination.is_symlink():
                        raise ProductionInstallError(
                            "production_activation_rollback_expected_absent_occupied"
                        )
                    disk_restore_status = "removed_to_previous_absence"
                    operation = "confirm_previous_absence"
                else:
                    raise ProductionInstallError(
                        "production_activation_previous_state_invalid"
                    )
                disk_restore_result = {
                    "operation": operation,
                    "label": label,
                    "is_production": is_production,
                    "exit_code": 0,
                    "restore_status": disk_restore_status,
                    "restore_sha256": restore_sha256,
                    "previous_mode": entry.get("previous_mode"),
                }
            except Exception as exc:
                disk_restore_result = {
                    "operation": "restore_launchagents_disk_state",
                    "label": label,
                    "is_production": is_production,
                    "exit_code": -1,
                    "exception_type": type(exc).__name__,
                    "restore_sha256": restore_sha256,
                }
                rollback_failures.append(
                    "rollback_restore_launchagents_disk_failed:"
                    f"{label}:{type(exc).__name__}"
                )
            audit["rollback_results"].append(disk_restore_result)

        for label in previously_loaded:
            entry = transaction_entries.get(label)
            restore_sha256 = (
                str(entry.get("previous_sha256", "") or "")
                if isinstance(entry, dict)
                else ""
            )
            try:
                if not isinstance(entry, dict):
                    raise ProductionInstallError(
                        "production_activation_restore_entry_missing"
                    )
                restore_path = _validated_restored_destination(
                    paths,
                    label=label,
                    entry=entry,
                )
            except ProductionInstallError as exc:
                rollback_failures.append(
                    "rollback_restore_previous_disk_invalid:"
                    f"{label}:{type(exc).__name__}"
                )
                audit["rollback_results"].append(
                    {
                        "operation": "restore_previous",
                        "label": label,
                        "exit_code": -1,
                        "restore_sha256": restore_sha256,
                    }
                )
                continue
            step, _ = _launchctl_call(
                launchctl_runner,
                "bootstrap",
                uid_domain,
                str(restore_path),
            )
            audit["launchctl_called_count"] += 1
            audit["steps"].append(
                {"phase": "rollback_restore_previous", "label": label, **step}
            )
            verify, verify_output = _launchctl_call(
                launchctl_runner,
                "print",
                f"{uid_domain}/{label}",
            )
            audit["launchctl_called_count"] += 1
            audit["steps"].append(
                {"phase": "rollback_verify_previous", "label": label, **verify}
            )
            try:
                restored_after_bootstrap = _validated_restored_destination(
                    paths,
                    label=label,
                    entry=entry,
                )
                restored_disk_confirmed = restored_after_bootstrap == restore_path
            except ProductionInstallError:
                restored_disk_confirmed = False
            loaded_state, _state, _pid, _classification = (
                classify_individual_launchctl_result(
                    exit_code=verify["exit_code"],
                    output=verify_output,
                    label=label,
                    uid=os.getuid(),
                )
            )
            restored_confirmed = loaded_state is True and restored_disk_confirmed
            audit["rollback_results"].append(
                {
                    "operation": "restore_previous",
                    "label": label,
                    "bootstrap_exit_code": step["exit_code"],
                    "verify_exit_code": verify["exit_code"],
                    "restored_confirmed": restored_confirmed,
                    "restored_disk_confirmed": restored_disk_confirmed,
                    "restore_sha256": restore_sha256,
                }
            )
            if restored_confirmed:
                audit["restored_labels"].append(label)
            else:
                rollback_failures.append(
                    "rollback_restore_previous_unconfirmed:"
                    f"{label}:bootstrap={step['exit_code']};"
                    f"verify={verify['exit_code']}"
                )

        # Re-read the complete owned launchd surface after restoration.  An
        # unrelated owned label that appeared after preflight is never
        # booted out by this transaction; it is reported separately while the
        # journal-owned disk/load state must still match exactly.
        rollback_surface = inspect_owned_launchd_surface(
            launchd_install_dir=paths.launchd_install_dir,
            allowed_production_labels=production_labels,
            known_conflicting_labels=CONFLICTING_JOB_LABELS,
            launchctl_runner=launchctl_runner,
        )
        audit["steps"].extend(rollback_surface["steps"])
        audit["launchctl_called_count"] += rollback_surface[
            "launchctl_called_count"
        ]
        known_target_labels = set(target_labels)
        expected_previous_disk = {
            label
            for label, entry in transaction_entries.items()
            if isinstance(entry, dict)
            and entry.get("previous_state") == "present"
        }
        expected_previous_loaded = set(previously_loaded)
        actual_known_disk = (
            set(rollback_surface["disk_owned_labels"])
            & known_target_labels
        )
        actual_known_domain = (
            set(rollback_surface["domain_owned_labels"])
            & known_target_labels
        )
        actual_known_loaded = (
            set(rollback_surface["loaded_owned_labels"])
            & known_target_labels
        )
        # A label outside the journal that appears while rollback is in
        # progress is not ours to mutate, but it also means the complete owned
        # surface cannot be proven restored.  Keep the rollback fail-closed and
        # require manual reconciliation instead of reporting a false success.
        structural_blockers = list(rollback_surface["blockers"])
        audit["rollback_owned_surface"] = {
            "status": rollback_surface["status"],
            "blockers": rollback_surface["blockers"],
            "unknown_owned_labels": rollback_surface[
                "unknown_owned_labels"
            ],
            "expected_known_disk_labels": sorted(expected_previous_disk),
            "actual_known_disk_labels": sorted(actual_known_disk),
            "expected_known_loaded_labels": sorted(
                expected_previous_loaded
            ),
            "actual_known_domain_labels": sorted(actual_known_domain),
            "actual_known_loaded_labels": sorted(actual_known_loaded),
        }
        if structural_blockers:
            rollback_failures.append(
                "rollback_owned_surface_unverified:"
                + ",".join(structural_blockers)
            )
        if actual_known_disk != expected_previous_disk:
            rollback_failures.append(
                "rollback_previous_disk_set_mismatch"
            )
        if actual_known_domain != expected_previous_loaded:
            rollback_failures.append(
                "rollback_previous_domain_set_mismatch"
            )
        if actual_known_loaded != expected_previous_loaded:
            rollback_failures.append(
                "rollback_previous_loaded_set_mismatch"
            )
        audit["rollback_failure_count"] = len(rollback_failures)
        audit["rollback_failures"] = rollback_failures
        audit["rollback_complete"] = not rollback_failures
        if rollback_failures:
            audit["status"] = "activation_failed_rollback_incomplete"
        else:
            audit["status"] = "activation_failed_rollback_complete"
        try:
            _set_plist_rollback_manifest_status(
                paths,
                status=(
                    "rollback_complete"
                    if not rollback_failures
                    else "rollback_incomplete"
                ),
                activation_manifest_sha256=str(
                    manifest.get("manifest_sha256", "")
                ),
            )
        except ProductionInstallError as exc:
            audit["rollback_failures"].append(
                f"rollback_manifest_status_write_failed:{type(exc).__name__}"
            )
            audit["rollback_failure_count"] = len(audit["rollback_failures"])
            audit["rollback_complete"] = False
            audit["status"] = "activation_failed_rollback_incomplete"
        _write_activation_audit(paths, audit)

    for label in target_labels:
        entry = transaction_entries.get(label)
        try:
            if not isinstance(entry, dict):
                raise ProductionInstallError(
                    f"production_activation_cas_entry_missing:{label}"
                )
            quarantined = _quarantine_journaled_destination(
                paths,
                label=label,
                entry=entry,
                quarantine_root=quarantine_root,
                suffix="original",
            )
            if quarantined is not None:
                quarantined_originals[label] = quarantined
        except BaseException as exc:
            rollback(f"journal_cas_failed:{label}:{type(exc).__name__}")
            raise ProductionActivationError(
                f"production_activation_journal_cas_failed:{label}",
                audit=audit,
            ) from exc
        step, _ = _launchctl_call(
            launchctl_runner,
            "bootout",
            f"{uid_domain}/{label}",
        )
        audit["launchctl_called_count"] += 1
        audit["steps"].append(
            {"phase": "ensure_target_absent", "label": label, **step}
        )
        verify, verify_output = _launchctl_call(
            launchctl_runner,
            "print",
            f"{uid_domain}/{label}",
        )
        audit["launchctl_called_count"] += 1
        audit["steps"].append(
            {"phase": "verify_target_absent", "label": label, **verify}
        )
        loaded_state, _state, _pid, _classification = (
            classify_individual_launchctl_result(
                exit_code=verify["exit_code"],
                output=verify_output,
                label=label,
                uid=os.getuid(),
            )
        )
        if loaded_state is not False:
            rollback(f"bootout_failed_or_unconfirmed:{label}")
            raise ProductionActivationError(
                f"production_activation_bootout_failed:{label}",
                audit=audit,
            )

    for label, entry in transaction_manifest.get(
        "conflict_entries", {}
    ).items():
        if entry.get("previous_state") != "present":
            continue
        try:
            destination = paths.launchd_install_dir / f"{label}.plist"
            if destination.exists() or destination.is_symlink():
                raise ProductionInstallError(
                    f"production_activation_quarantined_conflict_reappeared:{label}"
                )
            audit["steps"].append(
                {"phase": "quarantine_conflict_plist", "label": label, "exit_code": 0}
            )
        except BaseException as exc:
            audit["steps"].append(
                {
                    "phase": "remove_conflict_plist",
                    "label": label,
                    "exit_code": -1,
                    "exception_type": type(exc).__name__,
                }
            )
            rollback(f"remove_conflict_plist_failed:{label}")
            raise ProductionActivationError(
                f"production_activation_conflict_remove_failed:{label}",
                audit=audit,
            ) from exc

    for label in production_labels:
        staged = _staged_plist_path(paths, label)
        destination = paths.launchd_install_dir / f"{label}.plist"
        try:
            _publish_plist_expected_absent(staged, destination)
            published_production.add(label)
            install_status = "published_expected_absent"
            audit["steps"].append(
                {
                    "phase": "install_production_plist",
                    "label": label,
                    "install_status": install_status,
                    "exit_code": 0,
                }
            )
        except BaseException as exc:
            audit["steps"].append(
                {
                    "phase": "install_production_plist",
                    "label": label,
                    "exit_code": -1,
                    "exception_type": type(exc).__name__,
                }
            )
            rollback(f"install_production_plist_failed:{label}")
            raise ProductionActivationError(
                f"production_activation_plist_install_failed:{label}",
                audit=audit,
            ) from exc

    for label in production_labels:
        try:
            plist_path = paths.launchd_install_dir / f"{label}.plist"
            step, _ = _launchctl_call(
                launchctl_runner,
                "bootstrap",
                uid_domain,
                str(plist_path),
            )
            audit["launchctl_called_count"] += 1
            audit["steps"].append(
                {"phase": "bootstrap_production", "label": label, **step}
            )
            verify, verify_output = _launchctl_call(
                launchctl_runner,
                "print",
                f"{uid_domain}/{label}",
            )
            audit["launchctl_called_count"] += 1
            audit["steps"].append(
                {"phase": "verify_production_loaded", "label": label, **verify}
            )
            loaded_state, _state, _pid, _classification = (
                classify_individual_launchctl_result(
                    exit_code=verify["exit_code"],
                    output=verify_output,
                    label=label,
                    uid=os.getuid(),
                )
            )
            if step["exit_code"] != 0 or loaded_state is not True:
                raise ProductionInstallError(
                    f"bootstrap_failed_or_unconfirmed:{label}"
                )
            audit["bootstrapped_labels"].append(label)
        except BaseException as exc:
            rollback(f"bootstrap_failed_or_unconfirmed:{label}:{type(exc).__name__}")
            raise ProductionActivationError(
                f"production_activation_bootstrap_failed:{label}",
                audit=audit,
            ) from exc

    # Reboot/login must expose exactly the seven production definitions and no
    # known legacy/conflicting definition.
    try:
        for label in production_labels:
            installed = _strict_regular(
                paths.launchd_install_dir / f"{label}.plist"
            )
            staged = _strict_regular(_staged_plist_path(paths, label))
            if (
                stat.S_IMODE(installed.stat().st_mode) != 0o600
                or installed.read_bytes() != staged.read_bytes()
            ):
                raise ProductionInstallError(
                    f"production_disk_surface_invalid:{label}"
                )
        remaining_conflicts = [
            label
            for label in CONFLICTING_JOB_LABELS
            if (paths.launchd_install_dir / f"{label}.plist").exists()
            or (paths.launchd_install_dir / f"{label}.plist").is_symlink()
        ]
    except BaseException as exc:
        rollback(f"production_disk_surface_validation_failed:{type(exc).__name__}")
        raise ProductionActivationError(
            "production_activation_disk_surface_validation_failed",
            audit=audit,
        ) from exc
    if remaining_conflicts:
        rollback("conflict_disk_surface_not_empty")
        raise ProductionActivationError(
            "production_activation_conflict_disk_surface_not_empty",
            audit=audit,
        )

    try:
        final_surface = validate_exact_owned_launchd_surface(
            launchd_install_dir=paths.launchd_install_dir,
            allowed_production_labels=production_labels,
            known_conflicting_labels=CONFLICTING_JOB_LABELS,
            launchctl_runner=launchctl_runner,
        )
    except BaseException as exc:
        rollback(f"final_owned_surface_exception:{type(exc).__name__}")
        raise ProductionActivationError(
            "production_activation_final_owned_surface_exception",
            audit=audit,
        ) from exc
    audit["steps"].extend(final_surface["steps"])
    audit["launchctl_called_count"] += final_surface[
        "launchctl_called_count"
    ]
    audit["final_owned_surface"] = {
        key: final_surface[key]
        for key in (
            "status",
            "blockers",
            "disk_owned_labels",
            "domain_owned_labels",
            "loaded_owned_labels",
            "unknown_owned_labels",
            "disk_exact_production",
            "domain_exact_production",
            "loaded_exact_production",
        )
    }
    if final_surface["status"] != "verified_exact":
        rollback("final_owned_surface_not_exact")
        raise ProductionActivationError(
            "production_activation_final_owned_surface_not_exact:"
            + ",".join(final_surface["blockers"]),
            audit=audit,
        )

    expected_production = set(production_labels)
    final_disk_labels = set(final_surface["disk_owned_labels"])
    final_domain_labels = set(final_surface["domain_owned_labels"])
    final_loaded_labels = set(final_surface["loaded_owned_labels"])
    audit["launchd_surface_production_labels"] = sorted(
        final_loaded_labels & expected_production
    )
    audit["launchd_surface_production_loaded_count"] = len(
        final_loaded_labels & expected_production
    )
    audit["launchd_surface_conflict_loaded_count"] = len(
        final_loaded_labels - expected_production
    )
    audit["launchd_surface_loaded_owned_count"] = len(final_loaded_labels)
    audit["launchd_surface_domain_owned_count"] = len(final_domain_labels)
    audit["owned_surface_disk_fingerprints"] = final_surface[
        "disk_fingerprints"
    ]

    try:
        _set_plist_rollback_manifest_status(
            paths,
            status="activation_succeeded",
            activation_manifest_sha256=str(manifest.get("manifest_sha256", "")),
        )
    except BaseException as exc:
        rollback(
            "rollback_manifest_success_status_write_failed:"
            f"{type(exc).__name__}"
        )
        raise ProductionActivationError(
            "production_activation_rollback_manifest_finalize_failed",
            audit=audit,
        ) from exc
    audit["status"] = "production_launchd_activated_no_ctp_connection"
    audit["reboot_surface_production_plist_count"] = len(
        final_disk_labels & expected_production
    )
    audit["reboot_surface_conflict_plist_count"] = len(
        final_disk_labels - expected_production
    )
    try:
        _write_activation_audit(paths, audit)
    except BaseException as exc:
        rollback(
            "activation_success_audit_write_failed:"
            f"{type(exc).__name__}"
        )
        raise ProductionActivationError(
            "production_activation_success_audit_write_failed",
            audit=audit,
        ) from exc
    return audit


def prepare_stable_worktree(
    paths: ProductionInstallPaths,
    *,
    source_commit: str,
    _lock_held: bool = False,
) -> None:
    if not _lock_held:
        with _exclusive_install_lock(paths):
            prepare_stable_worktree(
                paths,
                source_commit=source_commit,
                _lock_held=True,
            )
        return
    if not _COMMIT_RE.fullmatch(source_commit):
        raise ProductionInstallError("production_install_source_commit_invalid")
    verified = _git(
        paths.main_repo,
        "rev-parse",
        "--verify",
        f"{source_commit}^{{commit}}",
    )
    if verified != source_commit:
        raise ProductionInstallError("production_install_source_commit_mismatch")
    if not paths.stable_repo.exists():
        paths.stable_repo.parent.mkdir(parents=True, exist_ok=True)
        _git(
            paths.main_repo,
            "worktree",
            "add",
            "--detach",
            str(paths.stable_repo),
            source_commit,
        )
    paths.stable_repo.chmod(0o700)
    if _git(paths.stable_repo, "rev-parse", "HEAD") != source_commit:
        raise ProductionInstallError("production_install_stable_head_mismatch")
    if _git(paths.stable_repo, "status", "--porcelain", "--untracked-files=all"):
        raise ProductionInstallError("production_install_stable_tree_not_clean")


def _validate_database(path: Path) -> None:
    _strict_regular(path)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ProductionInstallError("production_install_database_mode_invalid")
    try:
        connection = sqlite3.connect(
            f"file:{path.resolve(strict=True)}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ProductionInstallError("production_install_database_invalid") from exc
    if not row or row[0] != "ok":
        raise ProductionInstallError("production_install_database_quick_check_failed")


def _vt_setting_credentials_configured(path: Path) -> bool:
    _strict_regular(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProductionInstallError(
            "production_install_vt_setting_json_invalid"
        ) from exc
    if not isinstance(payload, dict):
        return False
    nested = payload.get("datafeed")
    username = payload.get("datafeed.username")
    password = payload.get("datafeed.password")
    if isinstance(nested, dict):
        username = username or nested.get("username")
        password = password or nested.get("password")
    return bool(str(username or "").strip() and str(password or "").strip())


def provision_stable_assets(
    paths: ProductionInstallPaths,
    *,
    _lock_held: bool = False,
) -> dict[str, Any]:
    if not _lock_held:
        with _exclusive_install_lock(paths):
            return provision_stable_assets(paths, _lock_held=True)
    _private_directory(paths.stable_repo)
    python_binary = (paths.main_venv / "bin/python").resolve(strict=True)
    python_metadata = python_binary.lstat()
    if (
        not stat.S_ISREG(python_metadata.st_mode)
        or python_metadata.st_uid != os.getuid()
    ):
        raise ProductionInstallError("production_install_python_owner_invalid")
    python_binary.chmod(0o755)
    _ensure_exact_symlink(paths.stable_repo / ".py311", paths.main_venv)
    _ensure_exact_symlink(
        paths.stable_portfolio / "backtest_outputs",
        paths.main_data,
    )
    validate_production_venv_link(
        declared_venv_link=paths.stable_repo / ".py311",
        expected_venv_root=paths.main_venv,
    )
    validate_production_data_link(
        declared_data_link=paths.stable_portfolio / "backtest_outputs",
        expected_data_root=paths.main_data,
    )

    for name in ("ctp_live.local.env", "official_live_email.local.env"):
        _copy_private_regular(
            paths.main_repo / "examples/portfolio_backtesting" / name,
            paths.stable_portfolio / name,
        )
    trader = _private_directory(paths.stable_trader)
    _copy_private_regular(
        paths.main_repo / ".vntrader/vt_setting.json",
        trader / "vt_setting.json",
        source_may_be_public_read=True,
    )
    if not _vt_setting_credentials_configured(trader / "vt_setting.json"):
        raise ProductionInstallError(
            "production_install_datafeed_credentials_missing"
        )
    database = trader / "database.db"
    if not database.exists():
        try:
            initialize_production_database_from_sqlite_backup(
                source_path=paths.main_repo / ".vntrader/database.db",
                destination_path=database,
            )
        except ProductionAssetError as exc:
            raise ProductionInstallError(
                "production_install_database_backup_failed"
            ) from exc
    _validate_database(database)
    if (trader / "connect_ctp.json").exists() or (
        trader / "connect_ctp.json"
    ).is_symlink():
        raise ProductionInstallError(
            "production_install_connect_ctp_copy_forbidden"
        )

    state_directories = (
        paths.state_root,
        paths.state_root / "runtime",
        paths.state_root / "runtime/state",
        paths.state_root / "official-live",
        paths.state_root / "signal-input",
        paths.state_root / "logs",
        paths.state_root / "data-readiness",
        paths.state_root / "health",
    )
    for directory in state_directories:
        _private_directory(directory)
    prepared_source_commit = _git(
        paths.stable_repo, "rev-parse", "--verify", "HEAD^{commit}"
    )
    if not _COMMIT_RE.fullmatch(prepared_source_commit):
        raise ProductionInstallError(
            "production_install_stable_head_invalid_for_rollback"
        )
    plist_staging_statuses, _staging_manifest = (
        _prepare_staged_production_plists(
            paths,
            prepared_source_commit=prepared_source_commit,
        )
    )

    status = _git(
        paths.stable_repo,
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    if status:
        raise ProductionInstallError("production_install_stable_tree_not_clean")
    return {
        "status": "production_assets_prepared_not_activated",
        "stable_tree_clean": True,
        "datafeed_credentials_configured": True,
        "production_plist_count": len(PRODUCTION_PLIST_NAMES),
        "production_plist_staging_statuses": plist_staging_statuses,
        "launchagents_written_count": 0,
        "launchctl_called_count": 0,
        "ctp_connection_attempted_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the exact private C9/15w production stable worktree and "
            "runtime assets. This stage never calls launchctl or CTP."
        )
    )
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--confirm-prepare", default="")
    parser.add_argument("--activate-prepared", action="store_true")
    parser.add_argument("--confirm-activate", default="")
    args = parser.parse_args()
    paths = canonical_install_paths()
    if args.activate_prepared:
        summary = activate_prepared_production(
            paths,
            confirmation=args.confirm_activate,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    if args.confirm_prepare != "I_UNDERSTAND_THIS_PREPARES_C9_15W_PRODUCTION_ASSETS":
        raise SystemExit("production_install_confirmation_missing")
    if not args.source_commit:
        raise SystemExit("production_install_source_commit_missing")
    with _exclusive_install_lock(paths):
        prepare_stable_worktree(
            paths,
            source_commit=args.source_commit,
            _lock_held=True,
        )
        summary = provision_stable_assets(paths, _lock_held=True)
    summary["source_commit"] = args.source_commit
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
