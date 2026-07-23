from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
from typing import Any, Mapping

from qmt_roll_official_live_daily_data_receipt import (
    build_and_write_production_daily_data_receipt,
)
from qmt_roll_official_live_failure_notify import (
    normalize_official_live_failure_blocker,
    notify_official_live_failure,
)
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_ENV,
    PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
    PHASE_D_SHADOW_REFRESH_ENV,
)
from run_qmt_roll_stage945_official_live_production_session_launcher import (
    PRODUCTION_ACTIVATION_RECEIPT,
    PRODUCTION_AI_ELIGIBILITY_PATH,
    PRODUCTION_DAILY_DATA_RECEIPT,
    PRODUCTION_DATABASE_PATH,
    PRODUCTION_DATA_LINK,
    PRODUCTION_DATA_ROOT,
    PRODUCTION_OUTPUT_ROOT,
    PRODUCTION_RELEASE_MANIFEST,
    PRODUCTION_RUNTIME_ROOT,
    PRODUCTION_SIGNAL_INPUT_ROOT,
    PYTHON_PATH,
    REPO_ROOT,
    ProductionSessionLaunchError,
    _assert_canonical_paths,
    _assert_stable_deploy_root,
    _resolve_target_date,
    _validate_code_qualification,
    _validate_daily_data_readiness,
    _validate_release_and_receipt,
)


PROJECT_DIR = Path(__file__).resolve().parent
_CANONICAL_SYSTEM_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PRODUCTION_EMAIL_CONFIG_PATH = PROJECT_DIR / "official_live_email.local.env"
PRODUCTION_VT_SETTING_PATH = REPO_ROOT / ".vntrader/vt_setting.json"
_EMAIL_REQUIRED_JOBS = {
    "day-close-readonly",
    "postclose-report",
    "monthly-ai-pool",
}
_DATAFEED_REQUIRED_JOBS = {
    "postclose-precompute",
    "monthly-ai-pool",
}
_STAGE935_OWNED_EMAIL_STATUSES = {
    "sent",
    "dry_run_written",
    "send_failed",
    "disabled",
    "blocked_missing_config",
}


@dataclass(frozen=True, slots=True)
class SupportJobSpec:
    job: str
    label: str
    script_name: str
    arguments: tuple[str, ...]
    gate_environment: tuple[tuple[str, str], ...] = ()
    writes_daily_data: bool = False


SUPPORT_JOB_SPECS = {
    "day-close-readonly": SupportJobSpec(
        job="day-close-readonly",
        label=(
            "local.qmt-roll.official-live.15w.c9-production-live-"
            "day-close-readonly"
        ),
        script_name="run_qmt_roll_stage907_official_live_readonly_refresh_gate.py",
        arguments=(
            "--mode",
            "refresh",
            "--env-profile",
            "production-live",
            "--wait-seconds",
            "30",
            "--confirm-readonly-refresh",
            PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
            "--email-policy",
            "always",
        ),
        gate_environment=((PHASE_D_READONLY_REFRESH_ENV, "1"),),
    ),
    "postclose-precompute": SupportJobSpec(
        job="postclose-precompute",
        label=(
            "local.qmt-roll.official-live.15w.c9-production-live-"
            "postclose-precompute"
        ),
        script_name="run_qmt_roll_stage909_official_live_shadow_refresh_gate.py",
        arguments=(
            "--execution-profile",
            "c9-15w",
            "--target-date-mode",
            "latest-completed",
            "--target-date-data-ready-time",
            "16:30",
            "--mode",
            "run",
            "--confirm-shadow-refresh",
            PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        ),
        gate_environment=((PHASE_D_SHADOW_REFRESH_ENV, "1"),),
        writes_daily_data=True,
    ),
    "postclose-report": SupportJobSpec(
        job="postclose-report",
        label=(
            "local.qmt-roll.official-live.15w.c9-production-live-"
            "postclose-report"
        ),
        script_name="run_qmt_roll_stage929_official_live_15w_timed_cycle.py",
        arguments=(
            "--phase",
            "post-close",
            "--shadow-refresh-mode",
            "plan-only",
            "--readonly-refresh-mode",
            "plan-only",
            "--ai-pool-preflight-mode",
            "check",
            "--email-policy",
            "always",
        ),
    ),
    "monthly-ai-pool": SupportJobSpec(
        job="monthly-ai-pool",
        label=(
            "local.qmt-roll.official-live.15w.c9-production-live-"
            "monthly-ai-pool"
        ),
        script_name="run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py",
        arguments=("--mode", "run", "--email-policy", "changes"),
    ),
    "health": SupportJobSpec(
        job="health",
        label="local.qmt-roll.official-live.15w.c9-production-live-health",
        script_name="run_qmt_roll_stage946_official_live_production_health_check.py",
        arguments=("--max-summary-age-seconds", "180"),
    ),
}


class ProductionSupportLaunchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        boundary: str = "pre-exec",
        downstream_email_attempted: bool = False,
    ) -> None:
        super().__init__(message)
        self.boundary = boundary
        self.downstream_email_attempted = downstream_email_attempted


def _canonical_support_owner(job: str) -> bool:
    spec = SUPPORT_JOB_SPECS[job]
    return (
        os.getppid() == 1
        and os.environ.get("XPC_SERVICE_NAME", "").strip() == spec.label
    )


def _resolve_support_target_date(
    environment: Mapping[str, str],
) -> tuple[str, dict[str, Any]]:
    try:
        return _resolve_target_date(environment)
    except (ProductionSessionLaunchError, subprocess.TimeoutExpired) as exc:
        raise ProductionSupportLaunchError(
            "production_support_target_date_resolver_failed",
            boundary="target-date-resolver",
        ) from exc


def build_support_command(spec: SupportJobSpec) -> list[str]:
    script = PROJECT_DIR / spec.script_name
    if not script.is_file() or script.is_symlink():
        raise ProductionSupportLaunchError(
            f"production_support_script_invalid:{spec.job}"
        )
    return [str(PYTHON_PATH), str(script), *spec.arguments]


def _build_support_environment(
    source: Mapping[str, str],
    *,
    spec: SupportJobSpec,
) -> dict[str, str]:
    account = pwd.getpwuid(os.getuid())
    label = str(source.get("XPC_SERVICE_NAME", "")).strip()
    if label != spec.label:
        raise ProductionSupportLaunchError(
            "production_support_xpc_label_invalid"
        )
    environment = {
        "HOME": account.pw_dir,
        "USER": account.pw_name,
        "LOGNAME": account.pw_name,
        "SHELL": account.pw_shell or "/bin/zsh",
        "PATH": _CANONICAL_SYSTEM_PATH,
        "TMPDIR": "/tmp",
        "XPC_SERVICE_NAME": label,
        "OFFICIAL_LIVE_OUTPUT_DIR": str(PRODUCTION_OUTPUT_ROOT.resolve(strict=True)),
        "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(
            PRODUCTION_SIGNAL_INPUT_ROOT.resolve(strict=True)
        ),
        "PYTHONUNBUFFERED": "1",
    }
    environment.update(dict(spec.gate_environment))
    if spec.job in _EMAIL_REQUIRED_JOBS:
        environment["OFFICIAL_LIVE_EMAIL_ENV_FILE"] = str(
            PRODUCTION_EMAIL_CONFIG_PATH
        )
    return environment


def _validate_private_runtime_file(path: Path, *, label: str) -> Path:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ProductionSupportLaunchError(
            f"production_support_{label}_missing"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise ProductionSupportLaunchError(
            f"production_support_{label}_security_invalid"
        )
    return path.resolve(strict=True)


def _validate_datafeed_credentials() -> None:
    path = _validate_private_runtime_file(
        PRODUCTION_VT_SETTING_PATH,
        label="vt_setting",
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProductionSupportLaunchError(
            "production_support_vt_setting_json_invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise ProductionSupportLaunchError(
            "production_support_datafeed_credentials_missing"
        )
    nested = payload.get("datafeed")
    username = payload.get("datafeed.username")
    password = payload.get("datafeed.password")
    if isinstance(nested, dict):
        username = username or nested.get("username")
        password = password or nested.get("password")
    if not str(username or "").strip() or not str(password or "").strip():
        raise ProductionSupportLaunchError(
            "production_support_datafeed_credentials_missing"
        )


def _validate_support_credentials(spec: SupportJobSpec) -> None:
    if spec.job in _EMAIL_REQUIRED_JOBS:
        _validate_private_runtime_file(
            PRODUCTION_EMAIL_CONFIG_PATH,
            label="email_config",
        )
    if spec.job in _DATAFEED_REQUIRED_JOBS:
        _validate_datafeed_credentials()


def _decode_final_json(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(stdout):
        if character != "{":
            continue
        try:
            payload, end = decoder.raw_decode(stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and not stdout[index + end :].strip():
            return payload
    raise ProductionSupportLaunchError(
        "production_support_precompute_summary_invalid"
    )


def _run_precompute_and_issue_daily_receipt(
    *,
    spec: SupportJobSpec,
    command: list[str],
    environment: Mapping[str, str],
    manifest: Mapping[str, Any],
) -> None:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=dict(environment),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.returncode != 0:
        raise ProductionSupportLaunchError(
            "production_support_precompute_process_failed"
        )
    summary = _decode_final_json(result.stdout)
    commands = summary.get("commands")
    if (
        summary.get("shadow_refresh_status") != "shadow_refresh_completed"
        or summary.get("execution_profile") != "c9-15w"
        or summary.get("refresh_attempted") != 1
        or not isinstance(commands, list)
        or not commands
        or any(
            not isinstance(row, dict) or row.get("exit_code") != 0
            for row in commands
        )
    ):
        raise ProductionSupportLaunchError(
            "production_support_precompute_not_qualified"
        )
    target_date = str(summary.get("target_date", ""))
    resolved_target, _resolver = _resolve_support_target_date(environment)
    if target_date != resolved_target:
        raise ProductionSupportLaunchError(
            "production_support_precompute_target_date_mismatch"
        )
    build_and_write_production_daily_data_receipt(
        output_path=PRODUCTION_DAILY_DATA_RECEIPT,
        declared_data_link=PRODUCTION_DATA_LINK,
        expected_data_root=PRODUCTION_DATA_ROOT,
        source_commit=str(manifest.get("source_commit", "")),
        manifest_sha256=str(manifest.get("manifest_sha256", "")),
        target_cutoff_date=target_date,
        production_database_path=PRODUCTION_DATABASE_PATH,
        signal_input_root=PRODUCTION_SIGNAL_INPUT_ROOT,
        official_ai_eligibility_path=PRODUCTION_AI_ELIGIBILITY_PATH,
        generated_at_utc=datetime.now(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        ),
    )


def _run_monthly_ai_pool_and_refresh_receipt(
    *,
    command: list[str],
    environment: Mapping[str, str],
    manifest: Mapping[str, Any],
) -> None:
    """Run Stage935, then bind any changed AI pool into a fresh daily cohort.

    Stage935 can replace the official eligibility file.  A receipt issued before
    that replacement would immediately become stale, so an actual update must
    be followed by the same qualified Stage909 precompute used post-close.  If
    the pool is already current, the existing receipt is revalidated and no
    expensive refresh is started.
    """

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=dict(environment),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    summary: dict[str, Any] = {}
    decode_error: ProductionSupportLaunchError | None = None
    try:
        summary = _decode_final_json(result.stdout)
    except ProductionSupportLaunchError as exc:
        decode_error = exc
    if result.returncode != 0:
        email_result = summary.get("email_result")
        email_status = (
            str(email_result.get("email_status", ""))
            if isinstance(email_result, dict)
            else ""
        )
        raise ProductionSupportLaunchError(
            "production_support_monthly_ai_pool_process_failed",
            boundary="monthly-stage935",
            downstream_email_attempted=(
                email_status in _STAGE935_OWNED_EMAIL_STATUSES
            ),
        ) from decode_error
    if decode_error is not None:
        raise decode_error
    status = str(summary.get("automation_status", ""))
    if status == "monthly_ai_pool_updated":
        precompute_spec = SUPPORT_JOB_SPECS["postclose-precompute"]
        precompute_environment = dict(environment)
        precompute_environment.update(dict(precompute_spec.gate_environment))
        try:
            _run_precompute_and_issue_daily_receipt(
                spec=precompute_spec,
                command=build_support_command(precompute_spec),
                environment=precompute_environment,
                manifest=manifest,
            )
        except Exception as exc:
            raise ProductionSupportLaunchError(
                "production_support_monthly_receipt_refresh_failed",
                boundary="monthly-receipt-refresh",
                downstream_email_attempted=False,
            ) from exc
        return
    if status != "monthly_ai_pool_already_current":
        raise ProductionSupportLaunchError(
            "production_support_monthly_ai_pool_not_qualified"
        )
    target_date, resolver = _resolve_support_target_date(environment)
    try:
        _validate_daily_data_readiness(
            manifest=manifest,
            target_date=target_date,
            resolver_payload=resolver,
        )
    except Exception as exc:
        raise ProductionSupportLaunchError(
            "production_support_monthly_existing_receipt_invalid",
            boundary="daily-data-receipt",
        ) from exc


def launch_support_job(args: argparse.Namespace) -> None:
    spec = SUPPORT_JOB_SPECS[args.job]
    label = str(os.environ.get("XPC_SERVICE_NAME", "")).strip()
    if os.getppid() != 1 or label != spec.label:
        raise ProductionSupportLaunchError(
            "production_support_requires_canonical_launchd_owner"
        )
    _assert_stable_deploy_root()
    _assert_canonical_paths(
        release_manifest=PRODUCTION_RELEASE_MANIFEST,
        activation_receipt=PRODUCTION_ACTIVATION_RECEIPT,
        runtime_root=PRODUCTION_RUNTIME_ROOT,
        output_root=PRODUCTION_OUTPUT_ROOT,
        signal_input_root=PRODUCTION_SIGNAL_INPUT_ROOT,
    )
    try:
        manifest = _validate_release_and_receipt(
            release_manifest=PRODUCTION_RELEASE_MANIFEST,
            activation_receipt=PRODUCTION_ACTIVATION_RECEIPT,
            runtime_root=PRODUCTION_RUNTIME_ROOT,
        )
        _validate_code_qualification(manifest=manifest)
    except Exception as exc:
        raise ProductionSupportLaunchError(
            "production_support_release_or_qualification_invalid"
        ) from exc
    environment = _build_support_environment(os.environ, spec=spec)
    _validate_support_credentials(spec)
    command = build_support_command(spec)
    if spec.job == "monthly-ai-pool":
        _run_monthly_ai_pool_and_refresh_receipt(
            command=command,
            environment=environment,
            manifest=manifest,
        )
        return
    if spec.writes_daily_data:
        _run_precompute_and_issue_daily_receipt(
            spec=spec,
            command=command,
            environment=environment,
            manifest=manifest,
        )
        return
    target_date, resolver = _resolve_support_target_date(environment)
    try:
        _validate_daily_data_readiness(
            manifest=manifest,
            target_date=target_date,
            resolver_payload=resolver,
        )
    except Exception as exc:
        raise ProductionSupportLaunchError(
            "production_support_daily_data_receipt_invalid",
            boundary="daily-data-receipt",
        ) from exc
    os.execve(str(PYTHON_PATH), command, environment)


def _print_blocked(job: str, blocker: str) -> None:
    print(
        json.dumps(
            {
                "model_tag": "stage947_production_support_launcher_v1",
                "generated_at": datetime.now().astimezone().isoformat(),
                "job": job,
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


def _notify_support_failure(
    *,
    job: str,
    boundary: str,
    blocker: str,
) -> None:
    notify_official_live_failure(
        job=job,
        boundary=boundary,
        blocker=blocker,
        schedule_date=datetime.now().astimezone().date().isoformat(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Pinned fail-closed launcher for C9/15w production support jobs."
        )
    )
    parser.add_argument("--job", choices=sorted(SUPPORT_JOB_SPECS), required=True)
    args = parser.parse_args()
    try:
        launch_support_job(args)
    except ProductionSupportLaunchError as exc:
        blocker = normalize_official_live_failure_blocker(
            str(exc),
            fallback="production_support_failure",
        )
        if (
            args.job != "health"
            and _canonical_support_owner(args.job)
            and not exc.downstream_email_attempted
        ):
            _notify_support_failure(
                job=args.job,
                boundary=exc.boundary,
                blocker=blocker,
            )
        _print_blocked(args.job, blocker)
        raise SystemExit(2)
    except Exception:
        blocker = "production_support_unexpected_failure"
        if args.job != "health" and _canonical_support_owner(args.job):
            _notify_support_failure(
                job=args.job,
                boundary="unexpected",
                blocker=blocker,
            )
        _print_blocked(args.job, blocker)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
