from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import subprocess
import time
from typing import Any

from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    PHASE_D_REAL_ENABLED_ENV,
    STAGE179_ACTIVATION_ENV,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    load_and_validate_release_manifest,
)
from build_qmt_roll_stage179_release_manifest import (
    load_and_validate_production_qualification_evidence,
)
from qmt_roll_official_live_daily_data_receipt import (
    load_and_validate_production_daily_data_receipt,
)
from qmt_roll_official_live_production_assets import (
    ProductionAssetError,
    validate_production_venv_link,
)
from qmt_roll_official_live_launchd_surface import (
    KNOWN_CONFLICTING_LABELS as SHARED_KNOWN_CONFLICTING_LABELS,
    PRODUCTION_LABELS as SHARED_PRODUCTION_LABELS,
    validate_exact_owned_launchd_surface,
)
from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile
from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import (
    validate_stage179_activation_receipt,
)
from run_qmt_roll_stage945_official_live_production_session_launcher import (
    PRODUCTION_ACTIVATION_RECEIPT,
    PRODUCTION_AI_ELIGIBILITY_PATH,
    PRODUCTION_DEPLOY_ROOT,
    PRODUCTION_DATA_LINK,
    PRODUCTION_DATA_ROOT,
    PRODUCTION_DATABASE_PATH,
    PRODUCTION_DAILY_DATA_RECEIPT,
    PRODUCTION_LABELS,
    PRODUCTION_MIN_FREE_BYTES,
    PRODUCTION_OUTPUT_ROOT,
    PRODUCTION_QUALIFICATION_EVIDENCE,
    PRODUCTION_RELEASE_MANIFEST,
    PRODUCTION_RUNTIME_ROOT,
    PRODUCTION_SIGNAL_INPUT_ROOT,
    PRODUCTION_STATE_ROOT,
    PRODUCTION_VENV_LINK,
    PRODUCTION_VENV_ROOT,
    REPO_ROOT,
    _active_session_names,
)


MODEL_TAG = "stage946_official_live_production_health_v1"
LAUNCHD_REPO_DIR = Path(__file__).resolve().parent / "launchd"
LAUNCHD_INSTALL_DIR = Path.home() / "Library" / "LaunchAgents"
PRODUCTION_SUPPORT_LABELS = {
    "day_close_readonly": (
        "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly"
    ),
    "postclose_precompute": (
        "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute"
    ),
    "postclose_report": (
        "local.qmt-roll.official-live.15w.c9-production-live-postclose-report"
    ),
    "monthly_ai_pool": (
        "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool"
    ),
    "health": "local.qmt-roll.official-live.15w.c9-production-live-health",
}
PRODUCTION_JOB_LABELS = {
    "day_session": PRODUCTION_LABELS["day"],
    "night_session": PRODUCTION_LABELS["night"],
    **PRODUCTION_SUPPORT_LABELS,
}
PRODUCTION_JOB_SCRIPT_NAMES = {
    "day_session": "run_qmt_roll_stage945_official_live_production_session_launcher.py",
    "night_session": "run_qmt_roll_stage945_official_live_production_session_launcher.py",
    "day_close_readonly": "run_qmt_roll_stage947_official_live_production_support_launcher.py",
    "postclose_precompute": "run_qmt_roll_stage947_official_live_production_support_launcher.py",
    "postclose_report": "run_qmt_roll_stage947_official_live_production_support_launcher.py",
    "monthly_ai_pool": "run_qmt_roll_stage947_official_live_production_support_launcher.py",
    "health": "run_qmt_roll_stage947_official_live_production_support_launcher.py",
}
PRODUCTION_SUPPORT_JOB_KEYS = {
    "day_close_readonly": "day-close-readonly",
    "postclose_precompute": "postclose-precompute",
    "postclose_report": "postclose-report",
    "monthly_ai_pool": "monthly-ai-pool",
    "health": "health",
}
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
if (
    tuple(PRODUCTION_JOB_LABELS.values()) != tuple(SHARED_PRODUCTION_LABELS)
    or tuple(CONFLICTING_JOB_LABELS)
    != tuple(SHARED_KNOWN_CONFLICTING_LABELS)
):
    raise RuntimeError("production_health_shared_launchd_labels_drift")
LATEST_STAGE930_SUMMARY = (
    PRODUCTION_OUTPUT_ROOT
    / "qmt_roll_official_live_c9_session_daemon_latest_summary.json"
)
READINESS_PATH = PRODUCTION_RUNTIME_ROOT / "state" / "executor_readiness.json"
HEALTH_ROOT = PRODUCTION_STATE_ROOT / "health"
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_RELEVANT_LABEL_PREFIXES = (
    "local.qmt-roll.official-live.",
    "local.qmt-roll.stage179.",
)
_FORBIDDEN_PLIST_ENV_KEYS = {
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "DYLD_LIBRARY_PATH",
    "LD_LIBRARY_PATH",
}
_SAFE_PLIST_ENV_VALUE_KEYS = {
    "OFFICIAL_LIVE_OUTPUT_DIR",
    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR",
    "OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED",
    "OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED",
    "OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED",
    "OFFICIAL_LIVE_PHASE_D_SHADOW_REFRESH_ENABLED",
    "PYTHONUNBUFFERED",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}
    return payload if isinstance(payload, dict) else {"_read_error": "not_object"}


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _launchctl_status(label: str) -> dict[str, Any]:
    result = subprocess.run(
        ["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=5,
        check=False,
    )
    row: dict[str, Any] = {
        "label": label,
        "loaded": result.returncode == 0,
        "state": "",
        "pid": None,
        "last_exit_code": None,
    }
    for line in result.stdout.splitlines():
        text = line.strip()
        if text.startswith("state = "):
            row["state"] = text.split("=", 1)[1].strip()
        elif text.startswith("pid = "):
            try:
                row["pid"] = int(text.split("=", 1)[1].strip())
            except ValueError:
                row["pid"] = None
        elif text.startswith("last exit code = "):
            row["last_exit_code"] = text.split("=", 1)[1].strip()
    return row


def _plist_status(
    label: str,
    *,
    launchctl_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = LAUNCHD_REPO_DIR / f"{label}.plist"
    installed = LAUNCHD_INSTALL_DIR / f"{label}.plist"
    source_bytes, source_payload, source_secure = _read_secure_plist(source)
    installed_bytes, installed_payload, installed_secure = _read_secure_plist(
        installed
    )
    installed_environment = installed_payload.get("EnvironmentVariables", {})
    if not isinstance(installed_environment, dict):
        installed_environment = {}
    program_arguments = installed_payload.get("ProgramArguments", [])
    if not isinstance(program_arguments, list):
        program_arguments = []
    forbidden_environment_keys = sorted(
        str(key)
        for key in installed_environment
        if str(key).startswith("CTP_")
        or str(key).upper() in _FORBIDDEN_PLIST_ENV_KEYS
        or any(
            token in str(key).upper()
            for token in (
                "PASSWORD",
                "AUTH_CODE",
                "USERID",
                "BROKERID",
                "TD_ADDRESS",
                "MD_ADDRESS",
                "APPID",
                "PRODUCT_INFO",
            )
        )
    )
    sanitized_environment = {
        str(key): (
            str(value)
            if str(key) in _SAFE_PLIST_ENV_VALUE_KEYS
            else "<redacted>"
        )
        for key, value in installed_environment.items()
    }
    return {
        "source_path": str(source),
        "installed_path": str(installed),
        "source_exists": source.exists(),
        "installed_exists": installed.exists(),
        "bytes_match": bool(source_bytes and source_bytes == installed_bytes),
        "source_secure": source_secure,
        "installed_secure": installed_secure,
        "label_match": (
            source_payload.get("Label") == label
            and installed_payload.get("Label") == label
        ),
        "working_directory": installed_payload.get("WorkingDirectory", ""),
        # Health output is persisted; retain only the executable/script prefix
        # so a malformed installed plist cannot turn it into a secret dump.
        "program_arguments": [str(item) for item in program_arguments[:4]],
        "environment_variables": sanitized_environment,
        "forbidden_environment_keys": forbidden_environment_keys,
        "launchctl": (
            _launchctl_status(label)
            if launchctl_row is None
            else dict(launchctl_row)
        ),
    }


def _read_secure_plist(path: Path) -> tuple[bytes, dict[str, Any], bool]:
    try:
        metadata = path.lstat()
        secure = bool(
            not stat.S_ISLNK(metadata.st_mode)
            and stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == os.getuid()
            and not (stat.S_IMODE(metadata.st_mode) & 0o022)
        )
        if not secure:
            return b"", {"_read_error": "plist_security_invalid"}, False
        raw = path.read_bytes()
        payload = plistlib.loads(raw)
        if not isinstance(payload, dict):
            return b"", {"_read_error": "plist_not_dictionary"}, False
        return raw, payload, True
    except Exception as exc:
        return b"", {"_read_error": repr(exc)}, False


def _discover_relevant_installed_labels() -> tuple[str, ...]:
    labels: set[str] = set()
    try:
        paths = tuple(LAUNCHD_INSTALL_DIR.glob("*.plist"))
    except OSError:
        return ()
    for path in paths:
        filename_label = path.stem
        if filename_label.startswith(_RELEVANT_LABEL_PREFIXES):
            labels.add(filename_label)
        _raw, payload, secure = _read_secure_plist(path)
        if not secure:
            continue
        payload_label = payload.get("Label")
        if isinstance(payload_label, str) and payload_label.startswith(
            _RELEVANT_LABEL_PREFIXES
        ):
            labels.add(payload_label)
    return tuple(sorted(labels))


def _age_seconds(path: Path) -> float | None:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return None


def _strict_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _path_has_symlink_component(path: Path) -> bool:
    candidate = Path(os.path.abspath(path.expanduser()))
    for component in tuple(reversed(candidate.parents)) + (candidate,):
        try:
            if stat.S_ISLNK(component.lstat().st_mode):
                return True
        except FileNotFoundError:
            continue
        except OSError:
            return True
    return False


def _directory_usage(path: Path, *, max_entries: int = 5_000) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": False,
        "bytes": 0,
        "file_count": 0,
        "directory_count": 0,
        "scan_truncated": False,
    }
    try:
        metadata = path.lstat()
    except OSError:
        return result
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        result["security_invalid"] = True
        return result
    result["exists"] = True
    stack = [path]
    entries = 0
    while stack:
        directory = stack.pop()
        try:
            children = tuple(os.scandir(directory))
        except OSError:
            result["scan_error"] = True
            break
        for child in children:
            entries += 1
            if entries > max_entries:
                result["scan_truncated"] = True
                return result
            try:
                child_stat = child.stat(follow_symlinks=False)
            except OSError:
                result["scan_error"] = True
                continue
            if stat.S_ISLNK(child_stat.st_mode):
                continue
            if stat.S_ISDIR(child_stat.st_mode):
                result["directory_count"] += 1
                stack.append(Path(child.path))
            elif stat.S_ISREG(child_stat.st_mode):
                result["file_count"] += 1
                result["bytes"] += int(child_stat.st_size)
    return result


def _build_storage_summary(*, minimum_free_bytes: int) -> dict[str, Any]:
    filesystems: list[dict[str, Any]] = []
    seen_devices: set[int] = set()
    for path in (PRODUCTION_STATE_ROOT, PRODUCTION_DATA_ROOT):
        try:
            resolved = path.resolve(strict=True)
            device = resolved.stat().st_dev
            usage = shutil.disk_usage(resolved)
        except OSError:
            filesystems.append(
                {
                    "path": str(path),
                    "available": False,
                    "below_minimum": True,
                }
            )
            continue
        if device in seen_devices:
            continue
        seen_devices.add(device)
        filesystems.append(
            {
                "path": str(resolved),
                "available": True,
                "total_bytes": int(usage.total),
                "used_bytes": int(usage.used),
                "free_bytes": int(usage.free),
                "minimum_free_bytes": minimum_free_bytes,
                "below_minimum": int(usage.free) < minimum_free_bytes,
            }
        )
    directory_paths = (
        PRODUCTION_STATE_ROOT / "logs",
        PRODUCTION_RUNTIME_ROOT,
        PRODUCTION_OUTPUT_ROOT,
        PRODUCTION_STATE_ROOT / "data-readiness",
        HEALTH_ROOT,
    )
    return {
        "minimum_free_bytes": minimum_free_bytes,
        "filesystems": filesystems,
        "directories": [_directory_usage(path) for path in directory_paths],
    }


def _daily_receipt_authorizes_active_session(
    receipt: dict[str, Any],
    *,
    current_sessions: tuple[str, ...],
    now: datetime,
) -> bool:
    target_date = str(receipt.get("target_cutoff_date", ""))
    inventory = receipt.get("data_inventory")
    semantic = inventory.get("semantic_freshness") if isinstance(inventory, dict) else None
    next_session = (
        str(semantic.get("next_trading_session_date", ""))
        if isinstance(semantic, dict)
        else ""
    )
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", next_session
    ):
        return False
    today = now.date().isoformat()
    if (
        now.weekday() == 5
        and "late_night" in current_sessions
        and now.hour < 3
    ):
        previous = (now.date() - timedelta(days=1)).isoformat()
        return target_date == previous
    before_data_ready = now.hour * 60 + now.minute < 16 * 60 + 30
    if before_data_ready:
        return next_session == today
    return target_date == today


def build_health_summary(
    *,
    max_summary_age_seconds: int = 180,
    minimum_free_bytes: int = PRODUCTION_MIN_FREE_BYTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    current = (now or datetime.now().astimezone()).astimezone()
    if type(minimum_free_bytes) is not int or minimum_free_bytes <= 0:
        blockers.append("production_storage_minimum_invalid")
        minimum_free_bytes = PRODUCTION_MIN_FREE_BYTES
    storage = _build_storage_summary(minimum_free_bytes=minimum_free_bytes)
    for row in storage["filesystems"]:
        if row.get("below_minimum"):
            blockers.append("production_free_disk_below_minimum")
    for row in storage["directories"]:
        if row.get("scan_truncated"):
            warnings.append(f"production_directory_usage_scan_truncated:{Path(row['path']).name}")
    if _path_has_symlink_component(PRODUCTION_DEPLOY_ROOT) or REPO_ROOT.resolve(
        strict=False
    ) != PRODUCTION_DEPLOY_ROOT.resolve(strict=False):
        blockers.append("production_repo_not_stable_deploy_root")
    try:
        validate_production_venv_link(
            declared_venv_link=PRODUCTION_VENV_LINK,
            expected_venv_root=PRODUCTION_VENV_ROOT,
        )
    except ProductionAssetError:
        blockers.append("production_venv_link_invalid")
    for field_name, path in (
        ("state_root", PRODUCTION_STATE_ROOT),
        ("release_manifest", PRODUCTION_RELEASE_MANIFEST),
        ("activation_receipt", PRODUCTION_ACTIVATION_RECEIPT),
        ("runtime_root", PRODUCTION_RUNTIME_ROOT),
        ("output_root", PRODUCTION_OUTPUT_ROOT),
        ("signal_input_root", PRODUCTION_SIGNAL_INPUT_ROOT),
    ):
        if _path_has_symlink_component(path):
            blockers.append(f"production_path_symlink_forbidden:{field_name}")
    try:
        owned_surface = validate_exact_owned_launchd_surface(
            launchd_install_dir=LAUNCHD_INSTALL_DIR,
            allowed_production_labels=tuple(PRODUCTION_JOB_LABELS.values()),
            known_conflicting_labels=CONFLICTING_JOB_LABELS,
        )
    except Exception as exc:
        owned_surface = {
            "status": "blocked",
            "blockers": [
                "owned_surface_inspection_failed:"
                f"{type(exc).__name__}"
            ],
            "disk_owned_labels": [],
            "domain_owned_labels": [],
            "loaded_owned_labels": [],
            "unknown_owned_labels": [],
            "jobs": {},
        }
    if owned_surface.get("status") != "verified_exact":
        blockers.append(
            "production_owned_launchd_surface_not_exact:"
            + ",".join(owned_surface.get("blockers", []))
        )
    surface_jobs = owned_surface.get("jobs", {})
    if not isinstance(surface_jobs, dict):
        surface_jobs = {}
    head = _git_head()
    jobs = {
        name: _plist_status(
            label,
            launchctl_row=(
                surface_jobs.get(label)
                if isinstance(surface_jobs.get(label), dict)
                else {
                    "label": label,
                    "loaded": None,
                    "state": "",
                    "pid": None,
                    "last_exit_code": None,
                }
            ),
        )
        for name, label in PRODUCTION_JOB_LABELS.items()
    }
    for name, row in jobs.items():
        if not row["source_exists"] or not row["installed_exists"]:
            blockers.append(f"production_job_plist_missing:{name}")
        if not row["bytes_match"] or not row["label_match"]:
            blockers.append(f"production_job_plist_mismatch:{name}")
        if not row["source_secure"] or not row["installed_secure"]:
            blockers.append(f"production_job_plist_security_invalid:{name}")
        if row["working_directory"] != str(PRODUCTION_DEPLOY_ROOT):
            blockers.append(f"production_job_working_directory_mismatch:{name}")
        expected_program_prefix = [
            str(PRODUCTION_DEPLOY_ROOT / ".py311/bin/python"),
            str(
                PRODUCTION_DEPLOY_ROOT
                / "examples/portfolio_backtesting"
                / PRODUCTION_JOB_SCRIPT_NAMES[name]
            ),
        ]
        expected_program_arguments = expected_program_prefix
        if name == "day_session":
            expected_program_arguments = [*expected_program_prefix, "--session", "day"]
        elif name == "night_session":
            expected_program_arguments = [*expected_program_prefix, "--session", "night"]
        elif name in PRODUCTION_SUPPORT_JOB_KEYS:
            expected_program_arguments = [
                *expected_program_prefix,
                "--job",
                PRODUCTION_SUPPORT_JOB_KEYS[name],
            ]
        if row["program_arguments"] != expected_program_arguments:
            blockers.append(f"production_job_program_mismatch:{name}")
        if row["forbidden_environment_keys"]:
            blockers.append(f"production_job_environment_secret_risk:{name}")
        environment = row["environment_variables"]
        expected_runtime_dirs = {
            "OFFICIAL_LIVE_OUTPUT_DIR": str(PRODUCTION_OUTPUT_ROOT),
            "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(PRODUCTION_SIGNAL_INPUT_ROOT),
        }
        if any(
            environment.get(key) != value
            for key, value in expected_runtime_dirs.items()
        ):
            blockers.append(f"production_job_runtime_root_mismatch:{name}")
        if name in {"day_session", "night_session"}:
            if (
                environment.get(PHASE_D_REAL_ENABLED_ENV) != "1"
                or environment.get(STAGE179_ACTIVATION_ENV) != "1"
            ):
                blockers.append(f"production_session_submit_gate_missing:{name}")
        elif (
            PHASE_D_REAL_ENABLED_ENV in environment
            or STAGE179_ACTIVATION_ENV in environment
        ):
            blockers.append(f"production_support_job_submit_gate_present:{name}")
        if row["launchctl"].get("loaded") is not True:
            blockers.append(f"production_job_not_loaded:{name}")

    discovered_labels = set(owned_surface.get("disk_owned_labels", []))
    unexpected_installed_labels = sorted(
        discovered_labels.difference(PRODUCTION_JOB_LABELS.values())
    )
    conflict_labels = sorted(
        set(CONFLICTING_JOB_LABELS)
        .union(unexpected_installed_labels)
        .union(owned_surface.get("unknown_domain_owned_labels", []))
        .union(owned_surface.get("unknown_loaded_owned_labels", []))
    )
    conflicts = {
        label: (
            dict(surface_jobs[label])
            if isinstance(surface_jobs.get(label), dict)
            else {
                "label": label,
                "loaded": None,
                "state": "",
                "pid": None,
                "last_exit_code": None,
            }
        )
        for label in conflict_labels
    }
    for label, row in conflicts.items():
        if row.get("loaded") is True:
            blockers.append(f"conflicting_launchd_job_loaded:{label}")
        if label in unexpected_installed_labels:
            blockers.append(f"unexpected_launchd_plist_installed:{label}")

    manifest: dict[str, Any] = {}
    daily_receipt: dict[str, Any] = {}
    qualification_evidence_sha256 = ""
    if not _COMMIT_RE.fullmatch(head):
        blockers.append("production_repo_head_invalid")
    else:
        try:
            manifest = load_and_validate_release_manifest(
                PRODUCTION_RELEASE_MANIFEST,
                repo_root=REPO_ROOT,
                expected_official_version=C9_15W_PROFILE.official_version,
                expected_capital=C9_15W_PROFILE.capital,
                expected_capital_label=C9_15W_PROFILE.capital_label,
                expected_execution_profile=C9_15W_PROFILE.profile_key,
                required_runtime_profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
                current_commit=head,
            )
        except (ReleaseManifestError, OSError, ValueError):
            blockers.append("production_release_manifest_invalid")
    if manifest:
        receipt_blockers = validate_stage179_activation_receipt(
            PRODUCTION_ACTIVATION_RECEIPT,
            manifest_sha256=str(manifest.get("manifest_sha256", "")),
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
        )
        blockers.extend(receipt_blockers)
        critical_paths = {
            str(item.get("path", ""))
            for item in manifest.get("critical_files", [])
            if isinstance(item, dict)
        }
        for label in PRODUCTION_JOB_LABELS.values():
            expected = f"examples/portfolio_backtesting/launchd/{label}.plist"
            if expected not in critical_paths:
                blockers.append(f"production_plist_not_manifest_bound:{label}")
        try:
            evidence = load_and_validate_production_qualification_evidence(
                PRODUCTION_QUALIFICATION_EVIDENCE,
                repo_root=REPO_ROOT,
                source_commit=str(manifest.get("source_commit", "")),
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
            qualification_evidence_sha256 = str(
                evidence.get("evidence_sha256", "")
            )
            qualification = manifest.get("strategy_semantics_qualification")
            if (
                not isinstance(qualification, dict)
                or qualification.get("status") != "passed"
                or qualification.get("evidence_id")
                != qualification_evidence_sha256
            ):
                blockers.append(
                    "production_qualification_evidence_manifest_mismatch"
                )
        except (ReleaseManifestError, OSError, ValueError):
            blockers.append("production_code_qualification_invalid")
        raw_receipt = _read_json(PRODUCTION_DAILY_DATA_RECEIPT)
        receipt_target_date = str(raw_receipt.get("target_cutoff_date", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", receipt_target_date):
            blockers.append("production_daily_data_receipt_target_invalid")
        else:
            try:
                daily_receipt = load_and_validate_production_daily_data_receipt(
                    PRODUCTION_DAILY_DATA_RECEIPT,
                    declared_data_link=PRODUCTION_DATA_LINK,
                    expected_data_root=PRODUCTION_DATA_ROOT,
                    source_commit=str(manifest.get("source_commit", "")),
                    manifest_sha256=str(manifest.get("manifest_sha256", "")),
                    target_cutoff_date=receipt_target_date,
                    production_database_path=PRODUCTION_DATABASE_PATH,
                    signal_input_root=PRODUCTION_SIGNAL_INPUT_ROOT,
                    official_ai_eligibility_path=PRODUCTION_AI_ELIGIBILITY_PATH,
                )
            except (ProductionAssetError, OSError, ValueError):
                blockers.append("production_daily_data_receipt_invalid")

    kill_switch = _read_json(KILL_SWITCH_PATH) if KILL_SWITCH_PATH.exists() else {}
    if kill_switch.get("_read_error"):
        blockers.append("kill_switch_unreadable")
    if bool(
        kill_switch.get("enabled", False)
        or kill_switch.get("kill_switch_active", False)
    ):
        blockers.append("kill_switch_active")

    current_sessions = _active_session_names(current)
    expected_label = ""
    if set(current_sessions) & {"night", "late_night"}:
        expected_label = PRODUCTION_LABELS["night"]
    elif set(current_sessions) & {"day_am", "day_pm"}:
        expected_label = PRODUCTION_LABELS["day"]
    calendar_status = "outside_session_window"
    if expected_label:
        if daily_receipt and _daily_receipt_authorizes_active_session(
            daily_receipt,
            current_sessions=current_sessions,
            now=current,
        ):
            calendar_status = "authorized_trading_session"
        elif daily_receipt:
            expected_label = ""
            calendar_status = "non_trading_day"
        else:
            calendar_status = "receipt_unavailable"
    session_statuses = {
        label: jobs[name]["launchctl"]
        for name, label in (
            ("day_session", PRODUCTION_LABELS["day"]),
            ("night_session", PRODUCTION_LABELS["night"]),
        )
    }
    running_labels = [
        label
        for label, row in session_statuses.items()
        if row.get("state") == "running" and row.get("pid")
    ]
    if len(running_labels) > 1:
        blockers.append("multiple_production_session_jobs_running")
    if expected_label:
        if expected_label not in running_labels:
            blockers.append("expected_production_session_not_running")
        if any(label != expected_label for label in running_labels):
            blockers.append("wrong_production_session_running")
    elif running_labels:
        blockers.append("production_session_running_outside_execution_window")

    latest = _read_json(LATEST_STAGE930_SUMMARY)
    summary_age = _age_seconds(LATEST_STAGE930_SUMMARY)
    readiness = _read_json(READINESS_PATH)
    if expected_label:
        if latest.get("_read_error") or summary_age is None:
            blockers.append("production_stage930_summary_missing")
        elif summary_age > max_summary_age_seconds:
            blockers.append("production_stage930_summary_stale")
        expected_identity = {
            "execution_profile": C9_15W_PROFILE.profile_key,
            "official_live_version": C9_15W_PROFILE.official_version,
            "capital": C9_15W_PROFILE.capital,
            "capital_label": C9_15W_PROFILE.capital_label,
            "runtime_profile": ExecutionRuntimeProfile.PRODUCTION_LIVE.value,
            "mode": "live-real",
            "submit_mode": "live-real",
            "detector_mode": "persistent",
            "daemon_status": "daemon_running",
        }
        for field_name, expected in expected_identity.items():
            if latest.get(field_name) != expected:
                blockers.append(f"production_stage930_identity_mismatch:{field_name}")
        target_date = str(latest.get("target_date", "")).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
            blockers.append("production_stage930_target_date_invalid")
        elif daily_receipt and target_date != daily_receipt.get("target_cutoff_date"):
            blockers.append("production_stage930_daily_receipt_target_mismatch")
        provenance = latest.get("launchd_provenance")
        if (
            not isinstance(provenance, dict)
            or provenance.get("complete") != 1
            or provenance.get("xpc_service_name") != expected_label
        ):
            blockers.append("production_stage930_launchd_provenance_invalid")
        else:
            expected_job_pid = session_statuses[expected_label].get("pid")
            if (
                type(expected_job_pid) is not int
                or expected_job_pid <= 0
                or provenance.get("pid") != expected_job_pid
                or provenance.get("launchctl_job_pid") != expected_job_pid
            ):
                blockers.append("production_stage930_launchd_pid_mismatch")
        for field_name in (
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
        ):
            if not _strict_nonnegative_int(latest.get(field_name)):
                blockers.append(f"production_stage930_api_count_invalid:{field_name}")
        if latest.get("order_api_evidence_complete") != 1:
            blockers.append("production_stage930_api_evidence_incomplete")
        if readiness.get("status") != "ready":
            blockers.append("production_warm_executor_not_ready")
        if readiness.get("schema_version") != 1:
            blockers.append("production_warm_executor_readiness_schema_mismatch")
        expires = readiness.get("expires_epoch_ns")
        if type(expires) is not int or expires <= time.time_ns():
            blockers.append("production_warm_executor_readiness_expired")
        if readiness.get("runtime_profile") != "production-live":
            blockers.append("production_warm_executor_profile_mismatch")
        if readiness.get("official_version") != C9_15W_PROFILE.official_version:
            blockers.append("production_warm_executor_version_mismatch")
        if readiness.get("capital") != C9_15W_PROFILE.capital:
            blockers.append("production_warm_executor_capital_mismatch")
        if not str(readiness.get("service_generation", "")).strip():
            blockers.append("production_warm_executor_service_generation_missing")
        if not str(readiness.get("connection_generation", "")).strip():
            blockers.append(
                "production_warm_executor_connection_generation_missing"
            )
        issued = readiness.get("issued_epoch_ns")
        if (
            type(issued) is not int
            or type(expires) is not int
            or issued <= 0
            or issued >= expires
        ):
            blockers.append("production_warm_executor_readiness_window_invalid")
    elif latest and summary_age is not None and summary_age <= max_summary_age_seconds:
        warnings.append("recent_stage930_summary_exists_outside_session")

    health_status = (
        "blocked"
        if blockers
        else (
            "healthy_production_live_session_running"
            if expected_label
            else "healthy_production_live_scheduled"
        )
    )
    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(),
        "health_status": health_status,
        "execution_profile": C9_15W_PROFILE.profile_key,
        "official_live_version": C9_15W_PROFILE.official_version,
        "capital": C9_15W_PROFILE.capital,
        "capital_label": C9_15W_PROFILE.capital_label,
        "runtime_profile": "production-live",
        "repo_root": str(REPO_ROOT),
        "repo_head": head,
        "manifest_sha256": manifest.get("manifest_sha256", ""),
        "qualification_evidence_sha256": qualification_evidence_sha256,
        "current_sessions": list(current_sessions),
        "calendar_status": calendar_status,
        "expected_session_label": expected_label,
        "running_session_labels": running_labels,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "production_jobs": jobs,
        "owned_launchd_surface": owned_surface,
        "conflicting_jobs": conflicts,
        "unexpected_installed_job_labels": unexpected_installed_labels,
        "latest_stage930_summary_path": str(LATEST_STAGE930_SUMMARY),
        "latest_stage930_summary_age_seconds": summary_age,
        "latest_stage930_summary": latest,
        "warm_executor_readiness": readiness,
        "kill_switch": kill_switch,
        "storage": storage,
        "send_order_api_called_count": latest.get("send_order_api_called_count", 0),
        "cancel_order_api_called_count": latest.get("cancel_order_api_called_count", 0),
        "order_api_called_count": latest.get("order_api_called_count", 0),
        "judgement": {
            "overfit_before": "否。生产健康检查不修改策略参数或信号。",
            "continue_before": "是。production-live 必须持续证明代码、manifest、receipt、launchd 与唯一进程一致。",
            "overfit_after": "否。检查结果只用于执行闸门和告警。",
            "continue_after": "是。任一阻断都应保持 fail-closed 并人工复核。",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="C9/15w production-live launchd and runtime health check."
    )
    parser.add_argument("--max-summary-age-seconds", type=int, default=180)
    parser.add_argument(
        "--min-free-bytes",
        type=int,
        default=PRODUCTION_MIN_FREE_BYTES,
    )
    args = parser.parse_args()
    summary = build_health_summary(
        max_summary_age_seconds=max(1, args.max_summary_age_seconds),
        minimum_free_bytes=max(1, args.min_free_bytes),
    )
    HEALTH_ROOT.mkdir(parents=True, mode=0o750, exist_ok=True)
    path = HEALTH_ROOT / "latest.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(0 if summary["health_status"] != "blocked" else 2)


if __name__ == "__main__":
    main()
