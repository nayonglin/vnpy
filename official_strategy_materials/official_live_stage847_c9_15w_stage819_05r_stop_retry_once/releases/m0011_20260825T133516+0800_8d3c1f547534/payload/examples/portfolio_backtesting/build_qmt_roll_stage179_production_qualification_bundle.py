from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import tempfile
import uuid
from typing import Any, Iterable, Mapping

from build_qmt_roll_stage179_release_manifest import (
    DEFAULT_CRITICAL_FILES,
    PRODUCTION_QUALIFICATION_EVIDENCE_KIND,
    PRODUCTION_QUALIFICATION_SCHEMA_VERSION,
    PRODUCTION_DIRECT_SCHEDULER_POLICY,
    PRODUCTION_PERFORMANCE_SCHEDULER_POLICY,
    PRODUCTION_PERFORMANCE_TASKPOLICY_PATH,
    PRODUCTION_PERFORMANCE_TEST_SUITE,
    PRODUCTION_REQUIRED_TEST_SUITES,
    _junit_counts,
    _production_runtime_identity,
    build_trusted_runner_environment,
    derive_formal_ctp_readonly_capture,
    load_and_validate_production_qualification_evidence,
    production_qualification_evidence_digest,
    serialize_production_qualification_evidence,
    trusted_runner_environment_receipt,
)
from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    READONLY_SUMMARY_PATH,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    release_critical_file_rows,
    release_tree_fingerprint,
)


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PRODUCTION_QUALIFICATION_RUN_CONFIRM_TEXT = (
    "I_APPROVE_RUNNING_EXACT_TESTS_AND_TWO_FORMAL_CTP_READONLY_CAPTURES"
)
STAGE174_READONLY_SUMMARY_FILENAME = READONLY_SUMMARY_PATH.name
STAGE907_SUMMARY_PREFIX = (
    "qmt_roll_stage907_official_live_readonly_refresh_gate_summary_"
)
# Process-local capability used only by the trusted orchestrator below.  Its
# identity cannot be serialized into caller-provided JSON/CLI arguments.  This
# prevents accidental bypass of the runner; it is not a security boundary
# against malicious code already executing as the same Unix user.
_TRUSTED_ASSEMBLER_SENTINEL = object()


def _trusted_pytest_argv(
    *,
    suite_id: str,
    python_realpath: str,
    junit_path: Path,
) -> tuple[list[str], str]:
    base_argv = [
        python_realpath,
        "-m",
        "pytest",
        "-q",
        suite_id,
        f"--junitxml={junit_path}",
        "-o",
        f"junit_suite_name={suite_id}",
        "-p",
        "no:cacheprovider",
    ]
    if suite_id != PRODUCTION_PERFORMANCE_TEST_SUITE:
        return base_argv, PRODUCTION_DIRECT_SCHEDULER_POLICY
    if platform.system() != "Darwin":
        raise ReleaseManifestError(
            "production_bundle_performance_taskpolicy_platform_invalid"
        )
    taskpolicy = Path(PRODUCTION_PERFORMANCE_TASKPOLICY_PATH)
    try:
        metadata = taskpolicy.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            "production_bundle_performance_taskpolicy_missing_or_invalid"
        ) from exc
    if (
        not taskpolicy.is_absolute()
        or stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or not os.access(taskpolicy, os.X_OK)
    ):
        raise ReleaseManifestError(
            "production_bundle_performance_taskpolicy_missing_or_invalid"
        )
    return (
        [str(taskpolicy), "-a", *base_argv],
        PRODUCTION_PERFORMANCE_SCHEDULER_POLICY,
    )


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseManifestError(
            f"production_bundle_git_failed:{' '.join(args)}"
        )
    return result.stdout.strip()


def _read_private_canonical_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    candidate = path.expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            f"production_bundle_input_missing:{candidate.name}"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ReleaseManifestError(
            f"production_bundle_input_security_invalid:{candidate.name}"
        )
    raw = candidate.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(
            f"production_bundle_input_json_invalid:{candidate.name}"
        ) from exc
    if (
        not isinstance(payload, dict)
        or raw != serialize_production_qualification_evidence(payload)
    ):
        raise ReleaseManifestError(
            f"production_bundle_input_not_canonical:{candidate.name}"
        )
    return raw, payload


def _read_private_bytes(path: Path) -> bytes:
    candidate = path.expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            f"production_bundle_input_missing:{candidate.name}"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ReleaseManifestError(
            f"production_bundle_input_security_invalid:{candidate.name}"
        )
    return candidate.read_bytes()


def _read_private_raw_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = _read_private_bytes(path)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(
            f"production_bundle_raw_json_invalid:{path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseManifestError(
            f"production_bundle_raw_json_invalid:{path.name}"
        )
    return raw, payload


def _read_owned_runtime_bytes(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            f"production_bundle_runtime_artifact_missing:{path.name}"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise ReleaseManifestError(
            f"production_bundle_runtime_artifact_security_invalid:{path.name}"
        )
    return path.read_bytes()


def _read_owned_runtime_json(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = _read_owned_runtime_bytes(path)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(
            f"production_bundle_runtime_artifact_json_invalid:{path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseManifestError(
            f"production_bundle_runtime_artifact_json_invalid:{path.name}"
        )
    return raw, payload


def _write_private_file(path: Path, raw: bytes) -> str:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return hashlib.sha256(raw).hexdigest()


def _copy_pointer(
    *,
    destination: Path,
    filename: str,
    raw: bytes,
) -> dict[str, str]:
    return {
        "artifact_path": filename,
        "artifact_sha256": _write_private_file(destination / filename, raw),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_clean_exact_repo(repo: Path, source_commit: str) -> None:
    if _git(repo, "rev-parse", "--verify", "HEAD^{commit}") != source_commit:
        raise ReleaseManifestError("production_bundle_runner_head_changed")
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseManifestError("production_bundle_runner_tree_changed")


def _assert_runtime_identity_unchanged(
    repo: Path,
    expected: Mapping[str, Any],
) -> None:
    if _production_runtime_identity(repo) != dict(expected):
        raise ReleaseManifestError(
            "production_bundle_runner_runtime_identity_changed"
        )


def _parse_single_json_stdout(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        start = text.find("{")
        if start < 0:
            raise ValueError("missing json object")
        payload, end = json.JSONDecoder().raw_decode(text[start:])
        if text[start + end :].strip():
            raise ValueError("unexpected trailing output")
    except Exception as exc:
        raise ReleaseManifestError(
            f"production_bundle_runner_stdout_invalid:{label}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseManifestError(
            f"production_bundle_runner_stdout_invalid:{label}"
        )
    return payload


def _runner_owned_environment(
    *,
    staging: Path,
    readonly: bool,
) -> tuple[dict[str, str], dict[str, Any]]:
    suffix = "readonly" if readonly else "pytest"
    home = staging / f"runner-{suffix}-home"
    temp_dir = staging / f"runner-{suffix}-tmp"
    for directory in (home, temp_dir):
        directory.mkdir(mode=0o700, exist_ok=False)
    environment = build_trusted_runner_environment(
        home=home,
        temp_dir=temp_dir,
        readonly=readonly,
    )
    return environment, trusted_runner_environment_receipt(
        environment,
        readonly=readonly,
    )


def _run_trusted_pytest_inputs(
    *,
    repo: Path,
    source_commit: str,
    staging: Path,
    runtime_identity: Mapping[str, Any],
    runner: Any = subprocess.run,
) -> tuple[
    dict[str, Path],
    dict[str, Path],
    list[dict[str, Any]],
    dict[str, Any],
]:
    junit_paths: dict[str, Path] = {}
    exit_paths: dict[str, Path] = {}
    invocations: list[dict[str, Any]] = []
    python_realpath = str(runtime_identity["python_realpath"])
    cwd_realpath = str(runtime_identity["cwd_realpath"])
    failed_suites: list[str] = []
    environment, environment_receipt = _runner_owned_environment(
        staging=staging,
        readonly=False,
    )
    _assert_runtime_identity_unchanged(repo, runtime_identity)
    for index, suite_id in enumerate(PRODUCTION_REQUIRED_TEST_SUITES):
        _assert_clean_exact_repo(repo, source_commit)
        junit_path = staging / f"raw-pytest-{index:02d}.xml"
        output_path = staging / f"raw-pytest-{index:02d}.output"
        exit_path = staging / f"raw-pytest-{index:02d}.exit-status"
        argv, scheduler_policy = _trusted_pytest_argv(
            suite_id=suite_id,
            python_realpath=python_realpath,
            junit_path=junit_path,
        )
        started_at = _utc_now()
        result = runner(
            argv,
            cwd=repo,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=900,
            check=False,
        )
        finished_at = _utc_now()
        output_raw = result.stdout
        if isinstance(output_raw, str):
            output_raw = output_raw.encode("utf-8")
        if not isinstance(output_raw, bytes):
            output_raw = b""
        _write_private_file(output_path, output_raw)
        _write_private_file(exit_path, f"{int(result.returncode)}\n".encode("ascii"))
        if not junit_path.exists():
            raise ReleaseManifestError(
                f"production_bundle_runner_junit_missing:{suite_id}"
            )
        junit_path.chmod(0o600)
        junit_raw = _read_private_bytes(junit_path)
        counts = _junit_counts(junit_raw, suite_id=suite_id)
        if (
            int(result.returncode) != 0
            or counts["passed_count"] <= 0
            or counts["failed_count"] != 0
            or counts["skipped_count"] != 0
        ):
            failed_suites.append(suite_id)
        _assert_clean_exact_repo(repo, source_commit)
        junit_paths[suite_id] = junit_path
        exit_paths[suite_id] = exit_path
        invocations.append(
            {
                "suite_id": suite_id,
                "invocation_nonce": uuid.uuid4().hex,
                "argv": argv,
                "started_at_utc": started_at,
                "finished_at_utc": finished_at,
                "returncode": int(result.returncode),
                "output_path": output_path,
                "environment_sha256": environment_receipt[
                    "environment_sha256"
                ],
                "scheduler_policy": scheduler_policy,
            }
        )
    if failed_suites:
        raise ReleaseManifestError(
            "production_bundle_runner_pytest_failed:"
            + ",".join(failed_suites)
        )
    _assert_runtime_identity_unchanged(repo, runtime_identity)
    return junit_paths, exit_paths, invocations, environment_receipt


def _run_trusted_readonly_inputs(
    *,
    repo: Path,
    source_commit: str,
    staging: Path,
    runtime_identity: Mapping[str, Any],
    runner: Any = subprocess.run,
) -> tuple[
    list[dict[str, Path]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    captures: list[dict[str, Path]] = []
    invocations: list[dict[str, Any]] = []
    python_realpath = str(runtime_identity["python_realpath"])
    runtime_output_dir = (
        repo / "examples/portfolio_backtesting/backtest_outputs"
    )
    stage174_summary_path = (
        runtime_output_dir / STAGE174_READONLY_SUMMARY_FILENAME
    )
    environment, environment_receipt = _runner_owned_environment(
        staging=staging,
        readonly=True,
    )
    stage907_script = (
        repo
        / "examples/portfolio_backtesting/"
        "run_qmt_roll_stage907_official_live_readonly_refresh_gate.py"
    )
    argv = [
        python_realpath,
        str(stage907_script),
        "--mode",
        "refresh",
        "--env-profile",
        "production-live",
        "--wait-seconds",
        "30",
        "--confirm-readonly-refresh",
        PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
        "--email-policy",
        "never",
    ]
    for index in range(2):
        _assert_runtime_identity_unchanged(repo, runtime_identity)
        _assert_clean_exact_repo(repo, source_commit)
        invocation_nonce = uuid.uuid4().hex
        started_at = _utc_now()
        result = runner(
            argv,
            cwd=repo,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
        finished_at = _utc_now()
        if int(result.returncode) != 0:
            raise ReleaseManifestError(
                f"production_bundle_runner_stage907_failed:{index}:"
                f"{int(result.returncode)}"
            )
        stdout_raw = result.stdout
        if isinstance(stdout_raw, str):
            stdout_raw = stdout_raw.encode("utf-8")
        if not isinstance(stdout_raw, bytes):
            stdout_raw = b""
        stage907 = _parse_single_json_stdout(
            stdout_raw,
            label=f"stage907-{index}",
        )
        outputs = stage907.get("outputs")
        if not isinstance(outputs, Mapping):
            raise ReleaseManifestError(
                f"production_bundle_runner_stage907_outputs_invalid:{index}"
            )
        stage907_summary_path = Path(str(outputs.get("summary_json", "")))
        try:
            stage907_summary_resolved = stage907_summary_path.resolve(
                strict=True
            )
            runtime_output_resolved = runtime_output_dir.resolve(strict=True)
        except OSError as exc:
            raise ReleaseManifestError(
                f"production_bundle_runner_stage907_output_path_invalid:{index}"
            ) from exc
        if (
            stage907_summary_resolved.parent != runtime_output_resolved
            or not stage907_summary_resolved.name.startswith(
                STAGE907_SUMMARY_PREFIX
            )
            or stage907_summary_resolved.suffix != ".json"
        ):
            raise ReleaseManifestError(
                f"production_bundle_runner_stage907_output_path_invalid:{index}"
            )
        stage907_raw, stage907_file = _read_owned_runtime_json(
            stage907_summary_resolved
        )
        if stage907_file != stage907:
            raise ReleaseManifestError(
                f"production_bundle_runner_stage907_stdout_mismatch:{index}"
            )
        stage174_raw, stage174 = _read_owned_runtime_json(
            stage174_summary_path
        )
        bundle = stage174.get("broker_query_bundle")
        artifacts = bundle.get("artifacts") if isinstance(bundle, Mapping) else None
        if not isinstance(artifacts, Mapping):
            raise ReleaseManifestError(
                f"production_bundle_runner_query_artifacts_missing:{index}"
            )
        capture_paths: dict[str, Path] = {}
        for name, raw in (
            ("stage907", stage907_raw),
            ("stage174", stage174_raw),
            ("stage907_stdout", stdout_raw),
        ):
            destination = staging / f"runner-{name}-{index:02d}.json"
            _write_private_file(destination, raw)
            capture_paths[name] = destination
        query_hashes: dict[str, str] = {}
        for name in ("orders", "trades", "positions"):
            row = artifacts.get(name)
            raw_path = Path(str(row.get("path", ""))) if isinstance(row, Mapping) else Path()
            try:
                raw_resolved = raw_path.resolve(strict=True)
                expected_parent = runtime_output_resolved
            except OSError as exc:
                raise ReleaseManifestError(
                    f"production_bundle_runner_query_artifact_path_invalid:{index}:{name}"
                ) from exc
            if raw_resolved.parent != expected_parent:
                raise ReleaseManifestError(
                    f"production_bundle_runner_query_artifact_path_invalid:{index}:{name}"
                )
            raw = _read_owned_runtime_bytes(raw_resolved)
            observed = hashlib.sha256(raw).hexdigest()
            if observed != (row or {}).get("sha256"):
                raise ReleaseManifestError(
                    f"production_bundle_runner_query_artifact_mismatch:{index}:{name}"
                )
            destination = staging / f"runner-{name}-{index:02d}.artifact"
            _write_private_file(destination, raw)
            capture_paths[name] = destination
            query_hashes[name] = observed
        account = bundle.get("account") if isinstance(bundle, Mapping) else None
        account_fingerprint = str(
            account.get("account_fingerprint", "")
            if isinstance(account, Mapping)
            else ""
        )
        if account_fingerprint != runtime_identity["account_fingerprint"]:
            raise ReleaseManifestError(
                f"production_bundle_runner_account_identity_mismatch:{index}"
            )
        derive_formal_ctp_readonly_capture(
            stage907_summary=stage907,
            stage174_summary=stage174,
            source_commit=source_commit,
            stage907_summary_artifact={
                "artifact_path": capture_paths["stage907"].name,
                "artifact_sha256": hashlib.sha256(stage907_raw).hexdigest(),
            },
            stage174_summary_artifact={
                "artifact_path": capture_paths["stage174"].name,
                "artifact_sha256": hashlib.sha256(stage174_raw).hexdigest(),
            },
            stage907_stdout_artifact={
                "artifact_path": capture_paths["stage907_stdout"].name,
                "artifact_sha256": hashlib.sha256(stdout_raw).hexdigest(),
            },
            query_artifacts={
                name: {
                    "artifact_path": capture_paths[name].name,
                    "artifact_sha256": query_hashes[name],
                }
                for name in ("orders", "trades", "positions")
            },
            env_identity_sha256=runtime_identity["env_identity_sha256"],
            formal_framework_realpaths=runtime_identity[
                "formal_framework_realpaths"
            ],
            python_sha256=runtime_identity["python_sha256"],
            vnpy_ctp_extension_sha256s=runtime_identity[
                "vnpy_ctp_extension_sha256s"
            ],
            formal_framework_executable_sha256s=runtime_identity[
                "formal_framework_executable_sha256s"
            ],
        )
        _assert_clean_exact_repo(repo, source_commit)
        _assert_runtime_identity_unchanged(repo, runtime_identity)
        captures.append(capture_paths)
        invocations.append(
            {
                "capture_index": index,
                "invocation_nonce": invocation_nonce,
                "argv": list(argv),
                "started_at_utc": started_at,
                "finished_at_utc": finished_at,
                "returncode": int(result.returncode),
                "account_fingerprint": account_fingerprint,
                "query_artifact_sha256s": query_hashes,
                "environment_sha256": environment_receipt[
                    "environment_sha256"
                ],
            }
        )
    return captures, invocations, environment_receipt


def _assemble_production_qualification_bundle(
    *,
    output_dir: Path | str,
    repo_root: Path | str,
    review_report: Path | str,
    pytest_junit_artifacts: Mapping[str, Path | str],
    pytest_exit_status_artifacts: Mapping[str, Path | str],
    formal_ctp_readonly_raw_captures: Iterable[Mapping[str, Path | str]],
    trusted_runner_context: Mapping[str, Any],
    critical_files: Iterable[str | Path] = DEFAULT_CRITICAL_FILES,
    generated_at_utc: str | None = None,
    _trusted_assembler_sentinel: object,
) -> Path:
    if _trusted_assembler_sentinel is not _TRUSTED_ASSEMBLER_SENTINEL:
        raise ReleaseManifestError(
            "production_bundle_trusted_assembler_capability_missing"
        )
    repo = Path(repo_root).expanduser().resolve(strict=True)
    destination = Path(output_dir).expanduser()
    if destination.exists():
        raise ReleaseManifestError("production_bundle_output_exists")
    destination_parent = destination.parent.resolve(strict=True)
    if destination_parent.is_relative_to(repo):
        raise ReleaseManifestError("production_bundle_output_must_be_external")
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseManifestError("production_bundle_requires_clean_tree")
    source_commit = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    critical = tuple(critical_files)
    critical_rows = release_critical_file_rows(
        repo_root=repo,
        critical_files=critical,
    )
    tree_fingerprint = release_tree_fingerprint(critical_rows)
    runtime_identity = _production_runtime_identity(repo)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )

    review_report_raw, review_report_payload = _read_private_canonical_json(
        Path(review_report)
    )
    if (
        review_report_payload.get("artifact_kind")
        != "independent_production_review_report"
        or review_report_payload.get("source_commit") != source_commit
        or review_report_payload.get("tree_fingerprint") != tree_fingerprint
    ):
        raise ReleaseManifestError(
            "production_bundle_review_report_source_mismatch"
        )
    findings = review_report_payload.get("findings")
    if not isinstance(findings, list):
        raise ReleaseManifestError("production_bundle_review_findings_invalid")
    review_counts = {
        f"{severity.lower()}_count": sum(
            1
            for finding in findings
            if isinstance(finding, dict)
            and finding.get("severity") == severity
            and finding.get("status") == "open"
        )
        for severity in ("P0", "P1", "P2")
    }

    junit_inputs = {
        str(suite_id): _read_private_bytes(Path(path))
        for suite_id, path in pytest_junit_artifacts.items()
    }
    exit_inputs = {
        str(suite_id): _read_private_bytes(Path(path))
        for suite_id, path in pytest_exit_status_artifacts.items()
    }
    if (
        set(junit_inputs) != set(PRODUCTION_REQUIRED_TEST_SUITES)
        or set(exit_inputs) != set(PRODUCTION_REQUIRED_TEST_SUITES)
    ):
        raise ReleaseManifestError("production_bundle_required_tests_missing")
    capture_inputs: list[dict[str, Any]] = []
    for index, capture_paths in enumerate(formal_ctp_readonly_raw_captures):
        if set(capture_paths) != {
            "stage907",
            "stage174",
            "stage907_stdout",
            "orders",
            "trades",
            "positions",
        }:
            raise ReleaseManifestError(
                f"production_bundle_readonly_capture_paths_invalid:{index}"
            )
        stage907_raw, stage907 = _read_private_raw_json(
            Path(capture_paths["stage907"])
        )
        stage174_raw, stage174 = _read_private_raw_json(
            Path(capture_paths["stage174"])
        )
        capture_inputs.append(
            {
                "stage907_raw": stage907_raw,
                "stage907": stage907,
                "stage174_raw": stage174_raw,
                "stage174": stage174,
                "stage907_stdout_raw": _read_private_bytes(
                    Path(capture_paths["stage907_stdout"])
                ),
                "query_raw": {
                    name: _read_private_bytes(Path(capture_paths[name]))
                    for name in ("orders", "trades", "positions")
                },
            }
        )
    if len(capture_inputs) < 2:
        raise ReleaseManifestError(
            "production_bundle_readonly_captures_missing"
        )
    pytest_runner_inputs = trusted_runner_context.get("pytest_invocations")
    readonly_runner_inputs = trusted_runner_context.get("readonly_invocations")
    pytest_environment_input = trusted_runner_context.get(
        "pytest_environment"
    )
    readonly_environment_input = trusted_runner_context.get(
        "readonly_environment"
    )
    if (
        trusted_runner_context.get("runner_mode") != "trusted_subprocess_v1"
        or not isinstance(trusted_runner_context.get("run_nonce"), str)
        or not isinstance(pytest_environment_input, Mapping)
        or not isinstance(readonly_environment_input, Mapping)
        or not isinstance(pytest_runner_inputs, list)
        or not isinstance(readonly_runner_inputs, list)
        or len(pytest_runner_inputs) != len(PRODUCTION_REQUIRED_TEST_SUITES)
        or len(readonly_runner_inputs) != len(capture_inputs)
    ):
        raise ReleaseManifestError("production_bundle_trusted_runner_context_invalid")
    pytest_runner_by_suite = {
        str(row.get("suite_id", "")): row
        for row in pytest_runner_inputs
        if isinstance(row, Mapping)
    }
    if set(pytest_runner_by_suite) != set(PRODUCTION_REQUIRED_TEST_SUITES):
        raise ReleaseManifestError("production_bundle_trusted_runner_tests_invalid")

    critical_hashes = {
        str(row["path"]): str(row["sha256"])
        for row in critical_rows
    }

    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination_parent,
        )
    )
    temporary.chmod(0o700)
    try:
        report_pointer = _copy_pointer(
            destination=temporary,
            filename="raw-independent-review-report.json",
            raw=review_report_raw,
        )
        review_summary = {
            "schema_version": 1,
            "artifact_kind": "independent_production_review",
            "review_kind": "independent",
            "review_id": review_report_payload.get("review_id"),
            "reviewer_identity": review_report_payload.get("reviewer_identity"),
            "reviewed_at_utc": review_report_payload.get("reviewed_at_utc"),
            "source_commit": source_commit,
            "tree_fingerprint": tree_fingerprint,
            **review_counts,
            "report_artifact_path": report_pointer["artifact_path"],
            "report_artifact_sha256": report_pointer["artifact_sha256"],
        }
        review_pointer = _copy_pointer(
            destination=temporary,
            filename="independent-review.json",
            raw=serialize_production_qualification_evidence(review_summary),
        )
        test_pointers: list[dict[str, str]] = []
        test_digests: dict[str, str] = {}
        trusted_pytest_rows: list[dict[str, Any]] = []
        test_totals = {"passed_count": 0, "failed_count": 0, "skipped_count": 0}
        for index, suite_id in enumerate(PRODUCTION_REQUIRED_TEST_SUITES):
            junit_raw = junit_inputs[suite_id]
            exit_raw = exit_inputs[suite_id]
            if not exit_raw.endswith(b"\n") or not exit_raw[:-1].isdigit():
                raise ReleaseManifestError(
                    f"production_bundle_pytest_exit_status_invalid:{suite_id}"
                )
            exit_code = int(exit_raw.decode("ascii").strip())
            counts = _junit_counts(junit_raw, suite_id=suite_id)
            junit_pointer = _copy_pointer(
                destination=temporary,
                filename=f"raw-pytest-{index:02d}.xml",
                raw=junit_raw,
            )
            exit_pointer = _copy_pointer(
                destination=temporary,
                filename=f"raw-pytest-{index:02d}.exit-status",
                raw=exit_raw,
            )
            runner_input = pytest_runner_by_suite[suite_id]
            output_raw = _read_private_bytes(Path(runner_input["output_path"]))
            output_pointer = _copy_pointer(
                destination=temporary,
                filename=f"raw-pytest-{index:02d}.output",
                raw=output_raw,
            )
            status = (
                "passed"
                if exit_code == 0 and counts["failed_count"] == 0
                else "failed"
            )
            test_summary = {
                "schema_version": 1,
                "artifact_kind": "pytest_suite_result",
                "suite_id": suite_id,
                "status": status,
                **counts,
                "source_commit": source_commit,
                "tree_fingerprint": tree_fingerprint,
                "test_file_sha256": critical_hashes.get(suite_id, ""),
                "generated_at_utc": generated,
                "pytest_exit_code": exit_code,
                "exit_status_artifact_path": exit_pointer["artifact_path"],
                "exit_status_artifact_sha256": exit_pointer["artifact_sha256"],
                "junit_artifact_path": junit_pointer["artifact_path"],
                "junit_artifact_sha256": junit_pointer["artifact_sha256"],
            }
            pointer = _copy_pointer(
                destination=temporary,
                filename=f"pytest-{index:02d}.json",
                raw=serialize_production_qualification_evidence(test_summary),
            )
            test_pointers.append({"suite_id": suite_id, **pointer})
            test_digests[suite_id] = pointer["artifact_sha256"]
            trusted_pytest_rows.append(
                {
                    "suite_id": suite_id,
                    "invocation_nonce": runner_input.get("invocation_nonce"),
                    "argv": runner_input.get("argv"),
                    "python_realpath": runtime_identity["python_realpath"],
                    "python_sha256": runtime_identity["python_sha256"],
                    "vnpy_ctp_extension_sha256s": runtime_identity[
                        "vnpy_ctp_extension_sha256s"
                    ],
                    "formal_framework_executable_sha256s": runtime_identity[
                        "formal_framework_executable_sha256s"
                    ],
                    "cwd_realpath": runtime_identity["cwd_realpath"],
                    "started_at_utc": runner_input.get("started_at_utc"),
                    "finished_at_utc": runner_input.get("finished_at_utc"),
                    "returncode": exit_code,
                    "test_file_sha256": critical_hashes.get(suite_id, ""),
                    "junit_artifact_sha256": junit_pointer["artifact_sha256"],
                    "exit_status_artifact_sha256": exit_pointer[
                        "artifact_sha256"
                    ],
                    "output_artifact_path": output_pointer["artifact_path"],
                    "output_artifact_sha256": output_pointer["artifact_sha256"],
                    "environment_sha256": runner_input.get(
                        "environment_sha256"
                    ),
                    "scheduler_policy": runner_input.get(
                        "scheduler_policy"
                    ),
                }
            )
            for field_name in test_totals:
                test_totals[field_name] += int(counts[field_name])
        aggregate_summary = {
            "schema_version": 1,
            "artifact_kind": "pytest_selected_suite_aggregate",
            "status": (
                "passed"
                if all(
                    int(exit_inputs[suite_id].decode("ascii").strip()) == 0
                    for suite_id in exit_inputs
                )
                and test_totals["failed_count"] == 0
                else "failed"
            ),
            "source_commit": source_commit,
            "tree_fingerprint": tree_fingerprint,
            "generated_at_utc": generated,
            "suite_ids": sorted(PRODUCTION_REQUIRED_TEST_SUITES),
            **test_totals,
            "result_artifact_sha256s": {
                key: test_digests[key] for key in sorted(test_digests)
            },
        }
        aggregate_pointer = _copy_pointer(
            destination=temporary,
            filename="selected-suite-aggregate.json",
            raw=serialize_production_qualification_evidence(aggregate_summary),
        )
        capture_pointers: list[dict[str, str]] = []
        captures: list[dict[str, Any]] = []
        trusted_readonly_rows: list[dict[str, Any]] = []
        for index, capture_input in enumerate(capture_inputs):
            stage907_raw = capture_input["stage907_raw"]
            stage907 = capture_input["stage907"]
            stage174_raw = capture_input["stage174_raw"]
            stage174 = capture_input["stage174"]
            stage907_pointer = _copy_pointer(
                destination=temporary,
                filename=f"raw-stage907-summary-{index:02d}.json",
                raw=stage907_raw,
            )
            stage174_pointer = _copy_pointer(
                destination=temporary,
                filename=f"raw-stage174-summary-{index:02d}.json",
                raw=stage174_raw,
            )
            stage907_stdout_pointer = _copy_pointer(
                destination=temporary,
                filename=f"raw-stage907-stdout-{index:02d}.json",
                raw=capture_input["stage907_stdout_raw"],
            )
            query_artifact_pointers = {
                name: _copy_pointer(
                    destination=temporary,
                    filename=f"raw-stage174-{name}-{index:02d}.artifact",
                    raw=capture_input["query_raw"][name],
                )
                for name in ("orders", "trades", "positions")
            }
            capture = derive_formal_ctp_readonly_capture(
                stage907_summary=stage907,
                stage174_summary=stage174,
                source_commit=source_commit,
                stage907_summary_artifact=stage907_pointer,
                stage174_summary_artifact=stage174_pointer,
                stage907_stdout_artifact=stage907_stdout_pointer,
                query_artifacts=query_artifact_pointers,
                env_identity_sha256=runtime_identity["env_identity_sha256"],
                formal_framework_realpaths=runtime_identity[
                    "formal_framework_realpaths"
                ],
                python_sha256=runtime_identity["python_sha256"],
                vnpy_ctp_extension_sha256s=runtime_identity[
                    "vnpy_ctp_extension_sha256s"
                ],
                formal_framework_executable_sha256s=runtime_identity[
                    "formal_framework_executable_sha256s"
                ],
            )
            pointer = _copy_pointer(
                destination=temporary,
                filename=f"derived-readonly-capture-{index:02d}.json",
                raw=serialize_production_qualification_evidence(capture),
            )
            capture_pointers.append(pointer)
            captures.append(capture)
            runner_input = readonly_runner_inputs[index]
            trusted_readonly_rows.append(
                {
                    "capture_index": index,
                    "invocation_nonce": runner_input.get("invocation_nonce"),
                    "argv": runner_input.get("argv"),
                    "python_realpath": runtime_identity["python_realpath"],
                    "python_sha256": runtime_identity["python_sha256"],
                    "vnpy_ctp_extension_sha256s": runtime_identity[
                        "vnpy_ctp_extension_sha256s"
                    ],
                    "formal_framework_executable_sha256s": runtime_identity[
                        "formal_framework_executable_sha256s"
                    ],
                    "cwd_realpath": runtime_identity["cwd_realpath"],
                    "started_at_utc": runner_input.get("started_at_utc"),
                    "finished_at_utc": runner_input.get("finished_at_utc"),
                    "returncode": int(runner_input.get("returncode", -1)),
                    "stage907_summary_sha256": stage907_pointer[
                        "artifact_sha256"
                    ],
                    "stage174_summary_sha256": stage174_pointer[
                        "artifact_sha256"
                    ],
                    "stage907_stdout_sha256": stage907_stdout_pointer[
                        "artifact_sha256"
                    ],
                    "account_fingerprint": capture["account_fingerprint"],
                    "env_identity_sha256": runtime_identity[
                        "env_identity_sha256"
                    ],
                    "formal_framework_realpaths": runtime_identity[
                        "formal_framework_realpaths"
                    ],
                    "python_sha256": runtime_identity["python_sha256"],
                    "vnpy_ctp_extension_sha256s": runtime_identity[
                        "vnpy_ctp_extension_sha256s"
                    ],
                    "formal_framework_executable_sha256s": runtime_identity[
                        "formal_framework_executable_sha256s"
                    ],
                    "query_artifact_sha256s": {
                        name: query_artifact_pointers[name]["artifact_sha256"]
                        for name in ("orders", "trades", "positions")
                    },
                    "environment_sha256": runner_input.get(
                        "environment_sha256"
                    ),
                }
            )
        broker_days = {
            str(capture.get("broker_trading_day", "")) for capture in captures
        }
        account_fingerprints = {
            str(capture.get("account_fingerprint", "")) for capture in captures
        }
        readonly_summary = {
            "schema_version": 1,
            "artifact_kind": "formal_ctp_readonly_qualification",
            "status": "qualified",
            "runtime_profile": "production-readonly",
            "env_profile": "ctp_live.local.env",
            "source_commit": source_commit,
            "generated_at_utc": generated,
            "capture_count": len(captures),
            "capture_invocation_ids": [
                str(capture.get("invocation_id", "")) for capture in captures
            ],
            "capture_query_generations": [
                str(capture.get("query_generation", "")) for capture in captures
            ],
            "broker_trading_day": (
                next(iter(broker_days)) if len(broker_days) == 1 else ""
            ),
            "account_fingerprint": (
                next(iter(account_fingerprints))
                if len(account_fingerprints) == 1
                else ""
            ),
            "env_identity_sha256": runtime_identity["env_identity_sha256"],
            "formal_framework_realpaths": runtime_identity[
                "formal_framework_realpaths"
            ],
            "python_sha256": runtime_identity["python_sha256"],
            "vnpy_ctp_extension_sha256s": runtime_identity[
                "vnpy_ctp_extension_sha256s"
            ],
            "formal_framework_executable_sha256s": runtime_identity[
                "formal_framework_executable_sha256s"
            ],
            "query_bundle_complete": int(
                all(capture.get("query_bundle_complete") == 1 for capture in captures)
            ),
            "account_query_complete": int(
                all(capture.get("account_query_complete") == 1 for capture in captures)
            ),
            "position_query_complete": int(
                all(capture.get("position_query_complete") == 1 for capture in captures)
            ),
            "order_query_complete": int(
                all(capture.get("order_query_complete") == 1 for capture in captures)
            ),
            "trade_query_complete": int(
                all(capture.get("trade_query_complete") == 1 for capture in captures)
            ),
            # Warm disconnect/reconnect is proven by the mandatory automated
            # fault suites in this same bundle, not by waiting indefinitely for
            # a natural front disconnect.
            "warm_disconnect_reconnect_fault_tests_passed": int(
                aggregate_summary["status"] == "passed"
            ),
            "natural_disconnect_reconnect_proof_observed": int(
                any(
                    capture.get("natural_disconnect_reconnect_proof_observed") == 1
                    for capture in captures
                )
            ),
            "capture_artifacts": capture_pointers,
            "send_order_api_called_count": sum(
                int(capture.get("send_order_api_called_count", -1))
                for capture in captures
            ),
            "cancel_order_api_called_count": sum(
                int(capture.get("cancel_order_api_called_count", -1))
                for capture in captures
            ),
            "order_api_called_count": sum(
                int(capture.get("order_api_called_count", -1))
                for capture in captures
            ),
        }
        readonly_pointer = _copy_pointer(
            destination=temporary,
            filename="formal-ctp-readonly.json",
            raw=serialize_production_qualification_evidence(readonly_summary),
        )
        trusted_runner = {
            "schema_version": 1,
            "artifact_kind": "production_qualification_runner_receipt",
            "runner_mode": "trusted_subprocess_v1",
            "source_commit": source_commit,
            "tree_fingerprint": tree_fingerprint,
            "python_realpath": runtime_identity["python_realpath"],
            "python_sha256": runtime_identity["python_sha256"],
            "vnpy_ctp_extension_sha256s": runtime_identity[
                "vnpy_ctp_extension_sha256s"
            ],
            "formal_framework_executable_sha256s": runtime_identity[
                "formal_framework_executable_sha256s"
            ],
            "formal_framework_realpaths": runtime_identity[
                "formal_framework_realpaths"
            ],
            "cwd_realpath": runtime_identity["cwd_realpath"],
            "run_nonce": trusted_runner_context.get("run_nonce"),
            "started_at_utc": trusted_runner_context.get("started_at_utc"),
            "finished_at_utc": trusted_runner_context.get("finished_at_utc"),
            "pytest_environment": dict(pytest_environment_input),
            "readonly_environment": dict(readonly_environment_input),
            "pytest_invocations": trusted_pytest_rows,
            "readonly_invocations": trusted_readonly_rows,
        }
        evidence: dict[str, Any] = {
            "schema_version": PRODUCTION_QUALIFICATION_SCHEMA_VERSION,
            "evidence_kind": PRODUCTION_QUALIFICATION_EVIDENCE_KIND,
            "generated_at_utc": generated,
            "source_commit": source_commit,
            "execution_profile": C9_15W_PROFILE.profile_key,
            "official_version": C9_15W_PROFILE.official_version,
            "capital": C9_15W_PROFILE.capital,
            "capital_label": C9_15W_PROFILE.capital_label,
            "critical_files": critical_rows,
            "tree_fingerprint": tree_fingerprint,
            "review": review_pointer,
            "required_tests": test_pointers,
            "selected_suite_aggregate": aggregate_pointer,
            "formal_ctp_readonly": readonly_pointer,
            "trusted_runner": trusted_runner,
        }
        evidence["evidence_sha256"] = production_qualification_evidence_digest(
            evidence
        )
        evidence_path = temporary / "qualification.json"
        _write_private_file(
            evidence_path,
            serialize_production_qualification_evidence(evidence),
        )
        load_and_validate_production_qualification_evidence(
            evidence_path,
            repo_root=repo,
            source_commit=source_commit,
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=critical,
            manifest_created_at_utc=generated,
        )
        _assert_clean_exact_repo(repo, source_commit)
        directory_fd = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        os.replace(temporary, destination)
        parent_fd = os.open(destination_parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return destination / "qualification.json"
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def build_trusted_production_qualification_bundle(
    *,
    output_dir: Path | str,
    repo_root: Path | str,
    review_report: Path | str,
    confirmation: str,
    critical_files: Iterable[str | Path] = DEFAULT_CRITICAL_FILES,
    generated_at_utc: str | None = None,
    runner: Any = subprocess.run,
) -> Path:
    """Run the production evidence commands instead of trusting caller files."""

    if confirmation != PRODUCTION_QUALIFICATION_RUN_CONFIRM_TEXT:
        raise ReleaseManifestError(
            "production_bundle_runner_confirmation_missing"
        )
    repo = Path(repo_root).expanduser().resolve(strict=True)
    destination = Path(output_dir).expanduser()
    destination_parent = destination.parent.resolve(strict=True)
    if destination_parent.is_relative_to(repo):
        raise ReleaseManifestError("production_bundle_output_must_be_external")
    if destination.exists():
        raise ReleaseManifestError("production_bundle_output_exists")
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseManifestError("production_bundle_requires_clean_tree")
    source_commit = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    normalized_critical_files = tuple(critical_files)
    material_current = repo / "official_strategy_materials/CURRENT.json"
    if material_current.is_file():
        from qmt_roll_official_strategy_material_resolver import (
            ActiveMaterialError,
            active_release_critical_files,
        )

        try:
            material_files = active_release_critical_files(
                repo_root=repo,
                require_deployable=True,
            )
        except ActiveMaterialError as exc:
            raise ReleaseManifestError(
                f"production_bundle_active_material_release_invalid:{exc}"
            ) from exc
        normalized_critical_files = tuple(
            dict.fromkeys((*normalized_critical_files, *material_files))
        )
    runtime_identity = _production_runtime_identity(repo)
    run_nonce = uuid.uuid4().hex
    started_at = _utc_now()
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.trusted-runner.",
            dir=destination_parent,
        )
    )
    staging.chmod(0o700)
    try:
        (
            junit_paths,
            exit_paths,
            pytest_invocations,
            pytest_environment,
        ) = (
            _run_trusted_pytest_inputs(
                repo=repo,
                source_commit=source_commit,
                staging=staging,
                runtime_identity=runtime_identity,
                runner=runner,
            )
        )
        (
            readonly_captures,
            readonly_invocations,
            readonly_environment,
        ) = (
            _run_trusted_readonly_inputs(
                repo=repo,
                source_commit=source_commit,
                staging=staging,
                runtime_identity=runtime_identity,
                runner=runner,
            )
        )
        finished_at = _utc_now()
        _assert_clean_exact_repo(repo, source_commit)
        _assert_runtime_identity_unchanged(repo, runtime_identity)
        return _assemble_production_qualification_bundle(
            output_dir=destination,
            repo_root=repo,
            review_report=review_report,
            pytest_junit_artifacts=junit_paths,
            pytest_exit_status_artifacts=exit_paths,
            formal_ctp_readonly_raw_captures=readonly_captures,
            trusted_runner_context={
                "runner_mode": "trusted_subprocess_v1",
                "run_nonce": run_nonce,
                "started_at_utc": started_at,
                "finished_at_utc": finished_at,
                "pytest_environment": pytest_environment,
                "readonly_environment": readonly_environment,
                "pytest_invocations": pytest_invocations,
                "readonly_invocations": readonly_invocations,
            },
            critical_files=normalized_critical_files,
            generated_at_utc=generated_at_utc or finished_at,
            _trusted_assembler_sentinel=_TRUSTED_ASSEMBLER_SENTINEL,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a canonical private C9/15w production qualification bundle "
            "by directly spawning the exact test and readonly commands."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--review-report", type=Path, required=True)
    parser.add_argument(
        "--confirm-trusted-production-qualification-run",
        required=True,
    )
    args = parser.parse_args()

    evidence_path = build_trusted_production_qualification_bundle(
        output_dir=args.output_dir,
        repo_root=args.repo_root,
        review_report=args.review_report,
        confirmation=args.confirm_trusted_production_qualification_run,
        critical_files=DEFAULT_CRITICAL_FILES,
        generated_at_utc=None,
    )
    print(evidence_path)


if __name__ == "__main__":
    main()
