from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from build_qmt_roll_stage179_release_manifest import (
    _production_runtime_identity,
    load_and_validate_production_qualification_evidence,
)
from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_phase_d_config import (
    STAGE179_ACTIVATION_RECEIPT_SCHEMA_VERSION,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    load_and_validate_release_manifest,
)
from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile
from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import (
    serialize_stage179_activation_receipt,
    stage179_activation_receipt_digest,
    validate_stage179_activation_receipt,
)


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PRODUCTION_ACTIVATION_RECEIPT_CONFIRM_TEXT = (
    "I_APPROVE_C9_15W_PRODUCTION_LIVE_ACTIVATION_RECEIPT"
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
            f"activation_receipt_git_failed:{' '.join(args)}"
        )
    return result.stdout.strip()


def build_stage179_activation_receipt(
    *,
    output_path: Path | str,
    release_manifest_path: Path | str,
    production_qualification_evidence: Path | str,
    confirmation: str,
    repo_root: Path | str = REPO_ROOT,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    if confirmation != PRODUCTION_ACTIVATION_RECEIPT_CONFIRM_TEXT:
        raise ReleaseManifestError("activation_receipt_confirmation_missing")
    repo = Path(repo_root).expanduser().resolve(strict=True)
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseManifestError("activation_receipt_requires_clean_tree")
    head = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    manifest = load_and_validate_release_manifest(
        release_manifest_path,
        repo_root=repo,
        expected_official_version=C9_15W_PROFILE.official_version,
        expected_capital=C9_15W_PROFILE.capital,
        expected_capital_label=C9_15W_PROFILE.capital_label,
        expected_execution_profile=C9_15W_PROFILE.profile_key,
        required_runtime_profile=ExecutionRuntimeProfile.PRODUCTION_LIVE,
        current_commit=head,
    )
    evidence = load_and_validate_production_qualification_evidence(
        production_qualification_evidence,
        repo_root=repo,
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
    activation_runtime_identity = _production_runtime_identity(repo)
    trusted_runner = evidence.get("trusted_runner")
    runtime_identity_fields = (
        "python_realpath",
        "python_sha256",
        "vnpy_ctp_extension_sha256s",
        "formal_framework_executable_sha256s",
        "formal_framework_realpaths",
    )
    if (
        not isinstance(trusted_runner, dict)
        or any(
            trusted_runner.get(field_name)
            != activation_runtime_identity.get(field_name)
            for field_name in runtime_identity_fields
        )
    ):
        raise ReleaseManifestError(
            "activation_receipt_runtime_binary_identity_mismatch"
        )
    qualification = manifest.get("strategy_semantics_qualification")
    if (
        not isinstance(qualification, dict)
        or qualification.get("status") != "passed"
        or qualification.get("evidence_id") != evidence.get("evidence_sha256")
    ):
        raise ReleaseManifestError(
            "activation_receipt_qualification_evidence_mismatch"
        )
    created = created_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    core: dict[str, Any] = {
        "schema_version": STAGE179_ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "manifest_sha256": str(manifest["manifest_sha256"]),
        "official_version": C9_15W_PROFILE.official_version,
        "capital": C9_15W_PROFILE.capital,
        "capital_label": C9_15W_PROFILE.capital_label,
        "policy_decision": "approved",
        "created_at_utc": created,
        "python_sha256": activation_runtime_identity["python_sha256"],
        "vnpy_ctp_extension_sha256s": activation_runtime_identity[
            "vnpy_ctp_extension_sha256s"
        ],
        "formal_framework_executable_sha256s": activation_runtime_identity[
            "formal_framework_executable_sha256s"
        ],
        "formal_framework_realpaths": activation_runtime_identity[
            "formal_framework_realpaths"
        ],
    }
    payload = {
        **core,
        "receipt_sha256": stage179_activation_receipt_digest(core),
    }
    destination = Path(output_path).expanduser()
    destination_parent = destination.parent.resolve(strict=True)
    if destination_parent.is_relative_to(repo):
        raise ReleaseManifestError("activation_receipt_output_must_be_external")
    encoded = serialize_stage179_activation_receipt(payload)
    if destination.exists():
        if destination.read_bytes() != encoded:
            raise ReleaseManifestError(
                "activation_receipt_refuses_different_overwrite"
            )
        return payload
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination_parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        parent_fd = os.open(destination_parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        temporary.unlink(missing_ok=True)
    blockers = validate_stage179_activation_receipt(
        destination,
        manifest_sha256=str(manifest["manifest_sha256"]),
        official_version=C9_15W_PROFILE.official_version,
        capital=C9_15W_PROFILE.capital,
        capital_label=C9_15W_PROFILE.capital_label,
        runtime_identity=activation_runtime_identity,
    )
    if blockers:
        destination.unlink(missing_ok=True)
        raise ReleaseManifestError(
            "activation_receipt_post_write_validation_failed:"
            + ",".join(blockers)
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Atomically issue a private activation receipt for an externally "
            "qualified C9/15w production-live manifest."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument(
        "--production-qualification-evidence",
        type=Path,
        required=True,
    )
    parser.add_argument("--confirm-production-activation", required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--created-at-utc", default="")
    args = parser.parse_args()
    payload = build_stage179_activation_receipt(
        output_path=args.output,
        release_manifest_path=args.release_manifest,
        production_qualification_evidence=(
            args.production_qualification_evidence
        ),
        confirmation=args.confirm_production_activation,
        repo_root=args.repo_root,
        created_at_utc=args.created_at_utc or None,
    )
    print(payload["receipt_sha256"])


if __name__ == "__main__":
    main()
