from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
from typing import Any, Mapping

from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
)
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ENABLED_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    STAGE179_ACTIVATION_CONFIRM_TEXT,
    STAGE179_ACTIVATION_ENV,
    build_phase_d_config,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    load_and_validate_release_manifest,
    release_manifest_digest,
    serialize_release_manifest,
)
from build_qmt_roll_stage179_release_manifest import (
    load_and_validate_production_qualification_evidence,
)
from qmt_roll_official_live_daily_data_receipt import (
    load_and_validate_production_daily_data_receipt,
)
from qmt_roll_official_live_failure_notify import (
    normalize_official_live_failure_blocker,
    notify_official_live_failure,
)
from qmt_roll_official_live_production_assets import (
    ProductionAssetError,
    validate_production_venv_link,
)
from qmt_roll_official_live_launchd_surface import (
    KNOWN_CONFLICTING_LABELS as OWNED_KNOWN_CONFLICTING_LABELS,
    PRODUCTION_LABELS as OWNED_PRODUCTION_LABELS,
    validate_exact_owned_launchd_surface,
)
from qmt_roll_official_live_runtime_profile import (
    ExecutionRuntimeProfile,
    OrderScope,
    resolve_runtime_profile,
)
from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import (
    validate_stage179_activation_receipt,
)


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PRODUCTION_DEPLOY_ROOT = (
    Path.home() / "Desktop" / "person" / "vnpy_production_live"
)
PRODUCTION_VENV_LINK = REPO_ROOT / ".py311"
PRODUCTION_VENV_ROOT = Path.home() / "Desktop/person/vnpy/.py311"
PYTHON_PATH = PRODUCTION_VENV_LINK / "bin/python"
STAGE922_SCRIPT = (
    PROJECT_DIR / "run_qmt_roll_stage922_official_live_target_date_resolver.py"
)
STAGE930_SCRIPT = (
    PROJECT_DIR / "run_qmt_roll_stage930_official_live_c9_session_daemon.py"
)
PRODUCTION_STATE_ROOT = (
    Path.home()
    / "Library"
    / "Application Support"
    / "qmt-roll-stage179"
    / "production-live"
)
PRODUCTION_RELEASE_MANIFEST = PRODUCTION_STATE_ROOT / "release-manifest.json"
PRODUCTION_ACTIVATION_AUDIT = (
    PRODUCTION_STATE_ROOT / "activation" / "latest.json"
)
PRODUCTION_LAUNCHD_INSTALL_DIR = Path.home() / "Library" / "LaunchAgents"
PRODUCTION_RUNTIME_ROOT = PRODUCTION_STATE_ROOT / "runtime"
PRODUCTION_ACTIVATION_RECEIPT = (
    PRODUCTION_RUNTIME_ROOT / "state" / "activation_receipt.json"
)
PRODUCTION_OUTPUT_ROOT = PRODUCTION_STATE_ROOT / "official-live"
PRODUCTION_SIGNAL_INPUT_ROOT = PRODUCTION_STATE_ROOT / "signal-input"
PRODUCTION_QUALIFICATION_EVIDENCE = (
    PRODUCTION_STATE_ROOT / "qualification-bundle" / "qualification.json"
)
PRODUCTION_DAILY_DATA_RECEIPT = (
    PRODUCTION_STATE_ROOT / "data-readiness" / "latest.json"
)
PRODUCTION_DATA_ROOT = (
    Path.home()
    / "Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs"
)
PRODUCTION_DATA_LINK = PROJECT_DIR / "backtest_outputs"
PRODUCTION_DATABASE_PATH = REPO_ROOT / ".vntrader" / "database.db"
PRODUCTION_AI_ELIGIBILITY_PATH = (
    PRODUCTION_DATA_LINK
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_"
    "eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)
PRODUCTION_LABELS = {
    "day": "local.qmt-roll.official-live.15w.c9-production-live-day-session",
    "night": "local.qmt-roll.official-live.15w.c9-production-live-night-session",
}
PRODUCTION_ACTIVATION_LABELS = (
    "local.qmt-roll.official-live.15w.c9-production-live-day-session",
    "local.qmt-roll.official-live.15w.c9-production-live-night-session",
    "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-report",
    "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool",
    "local.qmt-roll.official-live.15w.c9-production-live-health",
)
if tuple(PRODUCTION_ACTIVATION_LABELS) != tuple(OWNED_PRODUCTION_LABELS):
    raise RuntimeError("production_launcher_shared_launchd_labels_drift")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SAFE_OPTIONAL_ENV_KEYS = (
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "__CF_USER_TEXT_ENCODING",
)
_CANONICAL_SYSTEM_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PRODUCTION_MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SessionLaunchSpec:
    session: str
    label: str
    duration_seconds: int
    required_session_names: tuple[str, ...]


SESSION_SPECS = {
    "day": SessionLaunchSpec(
        session="day",
        label=PRODUCTION_LABELS["day"],
        duration_seconds=22_500,
        required_session_names=("day_am", "day_pm"),
    ),
    "night": SessionLaunchSpec(
        session="night",
        label=PRODUCTION_LABELS["night"],
        duration_seconds=20_400,
        required_session_names=("night", "late_night"),
    ),
}


class ProductionSessionLaunchError(RuntimeError):
    def __init__(self, message: str, *, boundary: str = "pre-exec") -> None:
        super().__init__(message)
        self.boundary = boundary


def _session_notification_schedule_date(
    session: str,
    now: datetime | None = None,
) -> str:
    current = (now or datetime.now().astimezone()).astimezone()
    day = current.date()
    if session == "night" and current.hour < 3:
        day -= timedelta(days=1)
    return day.isoformat()


def _canonical_session_owner(session: str) -> bool:
    spec = SESSION_SPECS[session]
    return (
        os.getppid() == 1
        and os.environ.get("XPC_SERVICE_NAME", "").strip() == spec.label
    )


def _assert_stable_deploy_root() -> None:
    _assert_no_symlink_components(
        PRODUCTION_DEPLOY_ROOT,
        field_name="deploy_root",
    )
    if PRODUCTION_DEPLOY_ROOT.is_symlink():
        raise ProductionSessionLaunchError(
            "production_launcher_deploy_root_symlink_forbidden"
        )
    try:
        observed = REPO_ROOT.resolve(strict=True)
        expected = PRODUCTION_DEPLOY_ROOT.resolve(strict=True)
    except OSError as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_stable_deploy_root_missing"
        ) from exc
    if observed != expected:
        raise ProductionSessionLaunchError(
            "production_launcher_noncanonical_deploy_root"
        )


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _assert_no_symlink_components(path: Path, *, field_name: str) -> None:
    candidate = _lexical_absolute(path)
    components = tuple(reversed(candidate.parents)) + (candidate,)
    for component in components:
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ProductionSessionLaunchError(
                f"production_launcher_path_lstat_failed:{field_name}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ProductionSessionLaunchError(
                f"production_launcher_path_symlink_forbidden:{field_name}"
            )


def _build_production_environment(
    source: Mapping[str, str],
    *,
    output_root: Path,
    signal_input_root: Path,
) -> dict[str, str]:
    account = pwd.getpwuid(os.getuid())
    label = str(source.get("XPC_SERVICE_NAME", "")).strip()
    if label not in PRODUCTION_LABELS.values():
        raise ProductionSessionLaunchError(
            "production_launcher_xpc_label_invalid"
        )
    environment = {
        "HOME": account.pw_dir,
        "USER": account.pw_name,
        "LOGNAME": account.pw_name,
        "SHELL": account.pw_shell or "/bin/zsh",
        "PATH": _CANONICAL_SYSTEM_PATH,
        "TMPDIR": "/tmp",
        "XPC_SERVICE_NAME": label,
        "OFFICIAL_LIVE_OUTPUT_DIR": str(output_root.resolve(strict=True)),
        "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(
            signal_input_root.resolve(strict=True)
        ),
        PHASE_D_REAL_ENABLED_ENV: "1",
        PHASE_D_SESSION_DAEMON_ENV: "1",
        STAGE179_ACTIVATION_ENV: "1",
        "PYTHONUNBUFFERED": "1",
    }
    for key in _SAFE_OPTIONAL_ENV_KEYS:
        value = str(source.get(key, "")).strip()
        if value:
            environment[key] = value
    return environment


def _build_preflight_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Build a sanitized environment without any live-enable capability."""

    account = pwd.getpwuid(os.getuid())
    environment = {
        "HOME": account.pw_dir,
        "USER": account.pw_name,
        "LOGNAME": account.pw_name,
        "SHELL": account.pw_shell or "/bin/zsh",
        "PATH": _CANONICAL_SYSTEM_PATH,
        "TMPDIR": "/tmp",
        "PYTHONUNBUFFERED": "1",
    }
    for key in _SAFE_OPTIONAL_ENV_KEYS:
        value = str(source.get(key, "")).strip()
        if value:
            environment[key] = value
    return environment


def _active_session_names(now: datetime | None = None) -> tuple[str, ...]:
    current = (now or datetime.now().astimezone()).astimezone()
    current_time = current.time().replace(tzinfo=None)
    names: list[str] = []
    for session in build_phase_d_config().sessions:
        start_hour, start_minute = [int(item) for item in session.start.split(":", 1)]
        end_hour, end_minute = [int(item) for item in session.end.split(":", 1)]
        start = current_time.replace(
            hour=start_hour,
            minute=start_minute,
            second=0,
            microsecond=0,
        )
        end = current_time.replace(
            hour=end_hour,
            minute=end_minute,
            second=0,
            microsecond=0,
        )
        active = start <= current_time <= end if start <= end else (
            current_time >= start or current_time <= end
        )
        if active:
            names.append(session.name)
    # Day/night starts are Monday-Friday.  A Friday night session may legally
    # continue into early Saturday, so late_night uses the previous weekday.
    if current.weekday() >= 5:
        if not (
            current.weekday() == 5
            and "late_night" in names
            and current.hour < 3
        ):
            names = []
    return tuple(names)


def _session_is_active(spec: SessionLaunchSpec, now: datetime | None = None) -> bool:
    return bool(set(_active_session_names(now)) & set(spec.required_session_names))


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise ProductionSessionLaunchError("production_launcher_git_head_unavailable")
    return result.stdout.strip()


def _strict_regular_file(path: Path, *, max_public_mode: int) -> None:
    if path.is_symlink():
        raise ProductionSessionLaunchError(
            f"production_launcher_symlink_forbidden:{path.name}"
        )
    try:
        metadata = path.stat()
    except OSError as exc:
        raise ProductionSessionLaunchError(
            f"production_launcher_file_missing:{path.name}"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ProductionSessionLaunchError(
            f"production_launcher_not_regular_file:{path.name}"
        )
    if metadata.st_uid != os.getuid():
        raise ProductionSessionLaunchError(
            f"production_launcher_file_owner_mismatch:{path.name}"
        )
    if stat.S_IMODE(metadata.st_mode) & max_public_mode:
        raise ProductionSessionLaunchError(
            f"production_launcher_file_permissions_too_open:{path.name}"
        )


def _read_private_json(path: Path, *, field_name: str) -> dict[str, Any]:
    _assert_no_symlink_components(path, field_name=field_name)
    _strict_regular_file(path, max_public_mode=0o077)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ProductionSessionLaunchError(
            f"production_launcher_private_file_mode_invalid:{field_name}"
        )
    try:
        raw = path.read_bytes()
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("oversized")
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ProductionSessionLaunchError(
            f"production_launcher_private_json_invalid:{field_name}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductionSessionLaunchError(
            f"production_launcher_private_json_not_mapping:{field_name}"
        )
    return payload


def _validate_activation_success_barrier(
    *,
    activation_audit: Path = PRODUCTION_ACTIVATION_AUDIT,
    release_manifest: Path = PRODUCTION_RELEASE_MANIFEST,
    expected_source_commit: str = "",
    expected_manifest_sha256: str = "",
) -> tuple[bool, str]:
    """Validate the activation commit before any runtime/data/CTP path."""

    try:
        audit = _read_private_json(
            activation_audit,
            field_name="activation_audit",
        )
        if audit.get("status") != "production_launchd_activated_no_ctp_connection":
            raise ProductionSessionLaunchError(
                "production_launcher_activation_status_not_committed"
            )
        audit_source_commit = str(audit.get("source_commit", "") or "")
        audit_manifest_sha256 = str(
            audit.get("manifest_sha256", "") or ""
        )
        if (
            not _COMMIT_RE.fullmatch(audit_source_commit)
            or not _SHA256_RE.fullmatch(audit_manifest_sha256)
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_identity_invalid"
            )
        expected_labels = list(PRODUCTION_ACTIVATION_LABELS)
        observed_surface_labels = audit.get(
            "launchd_surface_production_labels"
        )
        if (
            audit.get("production_labels") != expected_labels
            or not isinstance(observed_surface_labels, list)
            or len(observed_surface_labels) != len(expected_labels)
            or set(observed_surface_labels) != set(expected_labels)
            or audit.get("launchd_surface_production_loaded_count") != 7
            or audit.get("launchd_surface_conflict_loaded_count") != 0
            or audit.get("reboot_surface_production_plist_count") != 7
            or audit.get("reboot_surface_conflict_plist_count") != 0
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_label_surface_mismatch"
            )
        for field_name in (
            "ctp_connection_attempted_count",
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
        ):
            if audit.get(field_name) != 0:
                raise ProductionSessionLaunchError(
                    "production_launcher_activation_live_api_nonzero"
                )

        # Only a structurally final success audit is allowed to read and bind
        # the private release identity.  In-progress/rollback states stop above.
        release = _read_private_json(
            release_manifest,
            field_name="release_manifest_barrier",
        )
        raw_release = release_manifest.read_bytes()
        if raw_release != serialize_release_manifest(release):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_release_not_canonical"
            )
        release_sha256 = str(release.get("manifest_sha256", "") or "")
        source_commit = str(release.get("source_commit", "") or "")
        current_commit = _git_head()
        if (
            not _SHA256_RE.fullmatch(release_sha256)
            or release_manifest_digest(release) != release_sha256
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_release_digest_mismatch"
            )
        if (
            not _COMMIT_RE.fullmatch(source_commit)
            or source_commit != current_commit
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_release_commit_mismatch"
            )
        if activation_audit.stat().st_mtime_ns < release_manifest.stat().st_mtime_ns:
            raise ProductionSessionLaunchError(
                "production_launcher_activation_audit_stale"
            )
        if (
            audit_source_commit != source_commit
            or audit_manifest_sha256 != release_sha256
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_identity_mismatch"
            )
        if (
            expected_source_commit
            and source_commit != expected_source_commit
        ) or (
            expected_manifest_sha256
            and release_sha256 != expected_manifest_sha256
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_activation_revalidation_mismatch"
            )
    except Exception as exc:
        # This is a KeepAlive precondition, not a retryable runtime failure.
        # Any unreadable or internally unverifiable identity exits success at
        # the caller with every CTP/order counter still zero.
        return False, (
            "production_launcher_activation_barrier_unverified:"
            f"{type(exc).__name__}:{exc}"
        )
    return True, "activation_success_identity_verified"


def _validate_current_owned_launchd_surface(
    *,
    launchd_install_dir: Path = PRODUCTION_LAUNCHD_INSTALL_DIR,
    activation_audit: Path = PRODUCTION_ACTIVATION_AUDIT,
    launchctl_runner: Any = subprocess.run,
) -> tuple[bool, str]:
    """Revalidate disk, domain, jobs, and activation-bound fingerprints."""

    try:
        report = validate_exact_owned_launchd_surface(
            launchd_install_dir=launchd_install_dir,
            allowed_production_labels=tuple(PRODUCTION_ACTIVATION_LABELS),
            known_conflicting_labels=OWNED_KNOWN_CONFLICTING_LABELS,
            launchctl_runner=launchctl_runner,
        )
        if report.get("status") != "verified_exact":
            raise ProductionSessionLaunchError(
                "production_launcher_owned_surface_not_exact:"
                + ",".join(report.get("blockers", []))
            )
        audit = _read_private_json(
            activation_audit,
            field_name="activation_audit_surface_binding",
        )
        expected_fingerprints = audit.get(
            "owned_surface_disk_fingerprints"
        )
        if (
            not isinstance(expected_fingerprints, dict)
            or not expected_fingerprints
            or expected_fingerprints != report.get("disk_fingerprints")
        ):
            raise ProductionSessionLaunchError(
                "production_launcher_owned_surface_fingerprint_drift"
            )
    except Exception as exc:
        return False, (
            "production_launcher_owned_surface_unverified:"
            f"{type(exc).__name__}:{exc}"
        )
    return True, "current_owned_launchd_surface_verified_exact"


def _print_activation_barrier_skip(*, spec: SessionLaunchSpec, blocker: str) -> None:
    print(
        json.dumps(
            {
                "model_tag": "stage945_production_session_launcher_v1",
                "generated_at": datetime.now().astimezone().isoformat(),
                "session": spec.session,
                "launcher_status": "skipped_activation_not_committed",
                "activation_barrier_blocker": blocker,
                "production_live_environment_built_count": 0,
                "stage930_exec_called_count": 0,
                "ctp_connection_attempted_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _print_owned_surface_skip(*, spec: SessionLaunchSpec, blocker: str) -> None:
    print(
        json.dumps(
            {
                "model_tag": "stage945_production_session_launcher_v1",
                "generated_at": datetime.now().astimezone().isoformat(),
                "session": spec.session,
                "launcher_status": "skipped_owned_launchd_surface_unverified",
                "owned_launchd_surface_blocker": blocker,
                "production_live_environment_built_count": 0,
                "stage930_exec_called_count": 0,
                "ctp_connection_attempted_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _assert_canonical_paths(
    *,
    release_manifest: Path,
    activation_receipt: Path,
    runtime_root: Path,
    output_root: Path,
    signal_input_root: Path,
) -> None:
    observed = {
        "release_manifest": _lexical_absolute(release_manifest),
        "activation_receipt": _lexical_absolute(activation_receipt),
        "runtime_root": _lexical_absolute(runtime_root),
        "output_root": _lexical_absolute(output_root),
        "signal_input_root": _lexical_absolute(signal_input_root),
    }
    expected = {
        "release_manifest": _lexical_absolute(PRODUCTION_RELEASE_MANIFEST),
        "activation_receipt": _lexical_absolute(PRODUCTION_ACTIVATION_RECEIPT),
        "runtime_root": _lexical_absolute(PRODUCTION_RUNTIME_ROOT),
        "output_root": _lexical_absolute(PRODUCTION_OUTPUT_ROOT),
        "signal_input_root": _lexical_absolute(PRODUCTION_SIGNAL_INPUT_ROOT),
    }
    for field_name, expected_path in expected.items():
        if observed[field_name] != expected_path:
            raise ProductionSessionLaunchError(
                f"production_launcher_noncanonical_path:{field_name}"
            )
        _assert_no_symlink_components(
            observed[field_name],
            field_name=field_name,
        )
    for field_name in ("runtime_root", "output_root", "signal_input_root"):
        path = observed[field_name]
        if path.is_symlink() or not path.is_dir():
            raise ProductionSessionLaunchError(
                f"production_launcher_directory_invalid:{field_name}"
            )
        if stat.S_IMODE(path.stat().st_mode) & 0o027:
            raise ProductionSessionLaunchError(
                f"production_launcher_directory_permissions_too_open:{field_name}"
            )


def _resolve_target_date(environment: Mapping[str, str]) -> tuple[str, dict[str, Any]]:
    try:
        result = subprocess.run(
            [
                str(PYTHON_PATH),
                str(STAGE922_SCRIPT),
                "--data-ready-time",
                "16:30",
            ],
            cwd=REPO_ROOT,
            env=dict(environment),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_target_date_resolver_timeout",
            boundary="target-date-resolver",
        ) from exc
    if result.returncode != 0:
        raise ProductionSessionLaunchError(
            "production_launcher_target_date_resolver_failed"
        )
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_target_date_resolver_output_invalid"
        ) from exc
    target_date = str(payload.get("resolved_target_date", ""))
    evidence = payload.get("resolver_evidence")
    if not _DATE_RE.fullmatch(target_date) or not isinstance(evidence, dict):
        raise ProductionSessionLaunchError(
            "production_launcher_target_date_missing"
        )
    if payload.get("order_api_called_count") != 0:
        raise ProductionSessionLaunchError(
            "production_launcher_target_date_order_api_nonzero"
        )
    if evidence.get("trading_calendar_source") != "main_contract_mapping_trading_calendar":
        raise ProductionSessionLaunchError(
            "production_launcher_target_date_calendar_not_authoritative"
        )
    return target_date, payload


def _target_is_before_live_shadow_start(
    *,
    target_date: str,
    resolver_payload: Mapping[str, Any],
) -> bool:
    waiting_status = (
        "target_date_before_live_shadow_start_waiting_fail_closed"
    )
    if resolver_payload.get("resolver_status") != waiting_status:
        return False
    if (
        resolver_payload.get("resolved_target_date") != target_date
        or resolver_payload.get("official_live_shadow_analysis_start_date")
        != OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
        or resolver_payload.get("target_before_shadow_start") != 1
        or target_date >= OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
    ):
        raise ProductionSessionLaunchError(
            "production_launcher_live_shadow_cold_start_evidence_invalid"
        )
    return True


def _validate_target_date_calendar_window(
    *,
    receipt: Mapping[str, Any],
    resolver_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> str:
    evidence = resolver_payload.get("resolver_evidence")
    inventory = receipt.get("data_inventory")
    semantic = inventory.get("semantic_freshness") if isinstance(inventory, dict) else None
    if not isinstance(evidence, dict) or not isinstance(semantic, dict):
        raise ProductionSessionLaunchError(
            "production_launcher_calendar_evidence_missing"
        )
    current = (now or datetime.now().astimezone()).astimezone()
    try:
        resolver_as_of = datetime.fromisoformat(str(evidence.get("as_of", "")))
        ready_hour, ready_minute = [
            int(item) for item in str(evidence.get("data_ready_time", "")).split(":", 1)
        ]
    except (TypeError, ValueError) as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_calendar_evidence_invalid"
        ) from exc
    today = current.date().isoformat()
    if resolver_as_of.date().isoformat() != today:
        raise ProductionSessionLaunchError(
            "production_launcher_calendar_evidence_stale"
        )
    target_date = str(receipt.get("target_cutoff_date", ""))
    wall_clock_cutoff = str(evidence.get("wall_clock_cutoff_date", ""))
    next_session = str(semantic.get("next_trading_session_date", ""))
    if not all(
        _DATE_RE.fullmatch(value)
        for value in (target_date, wall_clock_cutoff, next_session)
    ):
        raise ProductionSessionLaunchError(
            "production_launcher_calendar_date_invalid"
        )
    current_minutes = current.hour * 60 + current.minute
    ready_minutes = ready_hour * 60 + ready_minute
    if current_minutes < ready_minutes:
        saturday_late_night_continuation = bool(
            current.weekday() == 5
            and "late_night" in _active_session_names(current)
            and target_date
            == (current.date() - timedelta(days=1)).isoformat()
        )
        if not saturday_late_night_continuation and next_session != today:
            if target_date < today < next_session:
                return "skipped_non_trading_day"
            raise ProductionSessionLaunchError(
                "production_launcher_today_not_authorized_next_trading_session"
            )
        if wall_clock_cutoff != target_date:
            # On the first session after a multi-day holiday, the naive weekday
            # cutoff lies inside the holiday.  The signed forward calendar is
            # the authority that permits the previous completed trading day.
            if next_session != today:
                raise ProductionSessionLaunchError(
                    "production_launcher_holiday_target_date_unqualified"
                )
    elif wall_clock_cutoff != target_date or target_date != today:
        if target_date < today < next_session:
            return "skipped_non_trading_day"
        raise ProductionSessionLaunchError(
            "production_launcher_after_close_target_date_mismatch"
        )
    return "authorized_trading_session"


def _assert_minimum_free_space(
    paths: tuple[Path, ...],
    *,
    minimum_free_bytes: int,
) -> None:
    if type(minimum_free_bytes) is not int or minimum_free_bytes <= 0:
        raise ProductionSessionLaunchError(
            "production_launcher_minimum_free_bytes_invalid"
        )
    checked_devices: set[int] = set()
    for path in paths:
        try:
            resolved = path.resolve(strict=True)
            device = resolved.stat().st_dev
            free_bytes = int(shutil.disk_usage(resolved).free)
        except OSError as exc:
            raise ProductionSessionLaunchError(
                f"production_launcher_storage_path_invalid:{path.name}"
            ) from exc
        if device in checked_devices:
            continue
        checked_devices.add(device)
        if free_bytes < minimum_free_bytes:
            raise ProductionSessionLaunchError(
                "production_launcher_free_disk_below_minimum"
            )


def build_stage930_command(
    *,
    spec: SessionLaunchSpec,
    target_date: str,
    release_manifest: Path = PRODUCTION_RELEASE_MANIFEST,
    activation_receipt: Path = PRODUCTION_ACTIVATION_RECEIPT,
    runtime_root: Path = PRODUCTION_RUNTIME_ROOT,
) -> list[str]:
    if not _DATE_RE.fullmatch(target_date):
        raise ProductionSessionLaunchError("production_launcher_target_date_invalid")
    command = [
        str(PYTHON_PATH),
        str(STAGE930_SCRIPT),
        "--execution-profile",
        C9_15W_PROFILE.profile_key,
        "--mode",
        "live-real",
        "--submit-mode",
        "live-real",
        "--runtime-profile",
        ExecutionRuntimeProfile.PRODUCTION_LIVE.value,
        "--stage179-execution-mode",
        "warm",
        "--detector-mode",
        "persistent",
        "--release-manifest",
        str(release_manifest),
        "--activation-receipt",
        str(activation_receipt),
        "--confirm-live-real",
        PHASE_D_CONFIRM_TEXT,
        "--confirm-stage179-activation",
        STAGE179_ACTIVATION_CONFIRM_TEXT,
        "--target-date",
        target_date,
        "--tick-refresh-mode",
        "stream",
        "--shadow-refresh-mode",
        "plan-only",
        "--readonly-refresh-mode",
        "auto",
        "--stage179-runtime-root",
        str(runtime_root),
        "--duration-seconds",
        str(spec.duration_seconds),
        "--max-cycles",
        "0",
        "--poll-seconds",
        "30",
        "--fast-poll-seconds",
        "1.0",
        "--detector-poll-seconds",
        "0.05",
        "--max-consecutive-cycle-errors",
        "3",
        "--ai-pool-preflight-mode",
        "check",
    ]
    for session_name in spec.required_session_names:
        command.extend(["--require-current-session-name", session_name])
    return command


def _validate_release_and_receipt(
    *,
    release_manifest: Path,
    activation_receipt: Path,
    runtime_root: Path,
) -> dict[str, Any]:
    runtime = resolve_runtime_profile(
        profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
        order_scope=OrderScope.LIVE,
        output_root=runtime_root,
        repo_root=REPO_ROOT,
    )
    if runtime.env_file is None:
        raise ProductionSessionLaunchError("production_launcher_live_env_missing")
    _strict_regular_file(runtime.env_file, max_public_mode=0o077)
    _strict_regular_file(release_manifest, max_public_mode=0o022)
    _strict_regular_file(activation_receipt, max_public_mode=0o077)
    if not STAGE930_SCRIPT.exists():
        raise ProductionSessionLaunchError("production_launcher_runtime_entry_missing")
    try:
        _venv_root, python_executable, framework_path = (
            validate_production_venv_link(
                declared_venv_link=PRODUCTION_VENV_LINK,
                expected_venv_root=PRODUCTION_VENV_ROOT,
            )
        )
    except ProductionAssetError as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_venv_link_invalid"
        ) from exc
    if (
        python_executable != PYTHON_PATH.resolve(strict=True)
        or len(runtime.framework_path) != 2
        or tuple(runtime.framework_path) != framework_path
        or runtime.framework_path[0] != framework_path[0]
    ):
        raise ProductionSessionLaunchError(
            "production_launcher_formal_ctp_framework_order_invalid"
        )
    try:
        manifest = load_and_validate_release_manifest(
            release_manifest,
            repo_root=REPO_ROOT,
            expected_official_version=C9_15W_PROFILE.official_version,
            expected_capital=C9_15W_PROFILE.capital,
            expected_capital_label=C9_15W_PROFILE.capital_label,
            expected_execution_profile=C9_15W_PROFILE.profile_key,
            required_runtime_profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
            current_commit=_git_head(),
        )
    except (ReleaseManifestError, OSError, ValueError) as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_release_manifest_invalid"
        ) from exc
    receipt_blockers = validate_stage179_activation_receipt(
        activation_receipt,
        manifest_sha256=str(manifest["manifest_sha256"]),
        official_version=C9_15W_PROFILE.official_version,
        capital=C9_15W_PROFILE.capital,
        capital_label=C9_15W_PROFILE.capital_label,
    )
    if receipt_blockers:
        raise ProductionSessionLaunchError(
            "production_launcher_activation_receipt_invalid:"
            + ",".join(receipt_blockers)
        )
    return manifest


def _validate_code_qualification(
    *,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    _strict_regular_file(PRODUCTION_QUALIFICATION_EVIDENCE, max_public_mode=0o077)
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
    except (ReleaseManifestError, OSError, ValueError) as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_code_qualification_invalid"
        ) from exc
    qualification = manifest.get("strategy_semantics_qualification")
    if (
        not isinstance(qualification, dict)
        or qualification.get("status") != "passed"
        or qualification.get("evidence_id") != evidence.get("evidence_sha256")
    ):
        raise ProductionSessionLaunchError(
            "production_launcher_qualification_evidence_mismatch"
        )
    return evidence


def _validate_daily_data_readiness(
    *,
    manifest: Mapping[str, Any],
    target_date: str,
    resolver_payload: Mapping[str, Any],
) -> dict[str, Any]:
    _strict_regular_file(PRODUCTION_DAILY_DATA_RECEIPT, max_public_mode=0o077)
    try:
        receipt = load_and_validate_production_daily_data_receipt(
            PRODUCTION_DAILY_DATA_RECEIPT,
            declared_data_link=PRODUCTION_DATA_LINK,
            expected_data_root=PRODUCTION_DATA_ROOT,
            source_commit=str(manifest.get("source_commit", "")),
            manifest_sha256=str(manifest.get("manifest_sha256", "")),
            target_cutoff_date=target_date,
            production_database_path=PRODUCTION_DATABASE_PATH,
            signal_input_root=PRODUCTION_SIGNAL_INPUT_ROOT,
            official_ai_eligibility_path=PRODUCTION_AI_ELIGIBILITY_PATH,
        )
    except (ProductionAssetError, OSError, ValueError) as exc:
        raise ProductionSessionLaunchError(
            "production_launcher_daily_data_receipt_invalid"
        ) from exc
    calendar_status = _validate_target_date_calendar_window(
        receipt=receipt,
        resolver_payload=resolver_payload,
    )
    return {**receipt, "production_calendar_status": calendar_status}


def launch_session(args: argparse.Namespace) -> None:
    spec = SESSION_SPECS[args.session]
    label = str(os.environ.get("XPC_SERVICE_NAME", "")).strip()
    if os.getppid() != 1 or label != spec.label:
        raise ProductionSessionLaunchError(
            "production_launcher_requires_canonical_launchd_owner"
        )
    _assert_stable_deploy_root()
    # The exact owned launchd surface is the outermost runtime authority.
    # Check it before the activation barrier reads the release identity, then
    # check it again immediately before building the live environment/exec.
    owned_surface_current, owned_surface_blocker = (
        _validate_current_owned_launchd_surface()
    )
    if not owned_surface_current:
        _print_owned_surface_skip(
            spec=spec,
            blocker=owned_surface_blocker,
        )
        return
    activation_committed, activation_blocker = (
        _validate_activation_success_barrier()
    )
    if not activation_committed:
        # KeepAlive(SuccessfulExit=false) starts these jobs at load and retries
        # only failures.  A missing/stale activation commit is therefore an
        # expected success exit, before release/runtime/data/CTP work.
        _print_activation_barrier_skip(
            spec=spec,
            blocker=activation_blocker,
        )
        return
    if not _session_is_active(spec):
        # This is an expected terminal condition for a launchd crash-restart
        # after the market window.  Returning success prevents KeepAlive from
        # spinning outside the authorized session.
        return
    release_manifest = Path(args.release_manifest)
    activation_receipt = Path(args.activation_receipt)
    runtime_root = Path(args.stage179_runtime_root)
    output_root = Path(args.output_root)
    signal_input_root = Path(args.signal_input_root)
    _assert_canonical_paths(
        release_manifest=release_manifest,
        activation_receipt=activation_receipt,
        runtime_root=runtime_root,
        output_root=output_root,
        signal_input_root=signal_input_root,
    )
    manifest = _validate_release_and_receipt(
        release_manifest=release_manifest,
        activation_receipt=activation_receipt,
        runtime_root=runtime_root,
    )
    activation_still_committed, activation_revalidation_blocker = (
        _validate_activation_success_barrier(
            expected_source_commit=str(manifest.get("source_commit", "")),
            expected_manifest_sha256=str(
                manifest.get("manifest_sha256", "")
            ),
        )
    )
    if not activation_still_committed:
        _print_activation_barrier_skip(
            spec=spec,
            blocker=activation_revalidation_blocker,
        )
        return
    preflight_environment = _build_preflight_environment(os.environ)
    target_date, resolver = _resolve_target_date(preflight_environment)
    _validate_code_qualification(
        manifest=manifest,
    )
    if _target_is_before_live_shadow_start(
        target_date=target_date,
        resolver_payload=resolver,
    ):
        # A deliberate cold start is an expected terminal condition.  Exit
        # successfully before requiring a pre-start daily-data receipt so
        # launchd KeepAlive(SuccessfulExit=false) does not retry in a loop.
        print(
            json.dumps(
                {
                    "model_tag": "stage945_production_session_launcher_v1",
                    "generated_at": datetime.now().astimezone().isoformat(),
                    "session": spec.session,
                    "launcher_status": "skipped_before_live_shadow_start",
                    "target_date": target_date,
                    "official_live_shadow_analysis_start_date": (
                        OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
                    ),
                    "stage930_exec_called_count": 0,
                    "ctp_connection_attempted_count": 0,
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                    "order_api_called_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    daily_receipt = _validate_daily_data_readiness(
        manifest=manifest,
        target_date=target_date,
        resolver_payload=resolver,
    )
    if daily_receipt.get("production_calendar_status") == "skipped_non_trading_day":
        print(
            json.dumps(
                {
                    "model_tag": "stage945_production_session_launcher_v1",
                    "generated_at": datetime.now().astimezone().isoformat(),
                    "session": spec.session,
                    "launcher_status": "skipped_non_trading_day",
                    "target_date": target_date,
                    "send_order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                    "order_api_called_count": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    _assert_minimum_free_space(
        (PRODUCTION_STATE_ROOT, PRODUCTION_DATA_ROOT),
        minimum_free_bytes=max(
            1,
            int(getattr(args, "min_free_bytes", PRODUCTION_MIN_FREE_BYTES)),
        ),
    )
    command = build_stage930_command(
        spec=spec,
        target_date=target_date,
        release_manifest=release_manifest.resolve(),
        activation_receipt=activation_receipt.resolve(),
        runtime_root=runtime_root.resolve(),
    )
    owned_surface_still_current, owned_surface_revalidation_blocker = (
        _validate_current_owned_launchd_surface()
    )
    if not owned_surface_still_current:
        _print_owned_surface_skip(
            spec=spec,
            blocker=owned_surface_revalidation_blocker,
        )
        return
    environment = _build_production_environment(
        os.environ,
        output_root=output_root,
        signal_input_root=signal_input_root,
    )
    os.execve(str(PYTHON_PATH), command, environment)


def _print_blocked(session: str, blocker: str) -> None:
    print(
        json.dumps(
            {
                "model_tag": "stage945_production_session_launcher_v1",
                "generated_at": datetime.now().astimezone().isoformat(),
                "session": session,
                "launcher_status": "blocked_fail_closed",
                "blocker": blocker,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed direct launchd entry for C9/15w production-live sessions."
        )
    )
    parser.add_argument("--session", choices=sorted(SESSION_SPECS), required=True)
    parser.add_argument(
        "--release-manifest",
        default=str(PRODUCTION_RELEASE_MANIFEST),
    )
    parser.add_argument(
        "--activation-receipt",
        default=str(PRODUCTION_ACTIVATION_RECEIPT),
    )
    parser.add_argument(
        "--stage179-runtime-root",
        default=str(PRODUCTION_RUNTIME_ROOT),
    )
    parser.add_argument("--output-root", default=str(PRODUCTION_OUTPUT_ROOT))
    parser.add_argument(
        "--signal-input-root",
        default=str(PRODUCTION_SIGNAL_INPUT_ROOT),
    )
    parser.add_argument(
        "--min-free-bytes",
        type=int,
        default=PRODUCTION_MIN_FREE_BYTES,
    )
    args = parser.parse_args()
    try:
        launch_session(args)
    except ProductionSessionLaunchError as exc:
        blocker = normalize_official_live_failure_blocker(
            str(exc),
            fallback="production_launcher_failure",
        )
        if _canonical_session_owner(args.session):
            notify_official_live_failure(
                job=f"{args.session}-session",
                boundary=exc.boundary,
                blocker=blocker,
                schedule_date=_session_notification_schedule_date(args.session),
            )
        _print_blocked(args.session, blocker)
        raise SystemExit(2)
    except Exception:
        blocker = "production_launcher_unexpected_failure"
        if _canonical_session_owner(args.session):
            notify_official_live_failure(
                job=f"{args.session}-session",
                boundary="unexpected",
                blocker=blocker,
                schedule_date=_session_notification_schedule_date(args.session),
            )
        _print_blocked(args.session, blocker)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
