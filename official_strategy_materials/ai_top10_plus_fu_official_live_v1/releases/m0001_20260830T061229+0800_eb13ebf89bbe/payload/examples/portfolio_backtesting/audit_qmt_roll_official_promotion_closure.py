from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
from typing import Any

from qmt_roll_official_baseline_identity import (
    OfficialBaselineIdentity,
    OfficialBaselineIdentityError,
    assert_official_checkout_matches_active_material,
)
from qmt_roll_strategy_material_manifest import canonical_json_bytes


PRODUCTION_PLIST_NAMES = (
    "local.qmt-roll.official-live.15w.c9-production-live-day-session.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-night-session.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist",
    "local.qmt-roll.official-live.15w.c9-production-live-health.plist",
)


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _git_value(repo: Path, *args: str) -> str:
    process = _run_git(repo, *args)
    if process.returncode != 0:
        raise RuntimeError("promotion_audit_git_read_failed")
    return process.stdout.strip()


def _json_object(path: Path, blocker: str, blockers: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        blockers.append(blocker)
        return None
    if not isinstance(payload, dict):
        blockers.append(blocker)
        return None
    return payload


def _referenced_json_object(
    bundle_root: Path,
    qualification: dict[str, Any] | None,
    field: str,
    blockers: list[str],
) -> dict[str, Any] | None:
    blocker_prefix = f"production_{field}"
    if qualification is None or not isinstance(qualification.get(field), dict):
        blockers.append(f"{blocker_prefix}_reference_missing")
        return None
    reference = qualification[field]
    artifact_path = reference.get("artifact_path")
    expected_sha256 = reference.get("artifact_sha256")
    if not isinstance(artifact_path, str) or not artifact_path:
        blockers.append(f"{blocker_prefix}_artifact_path_missing")
        return None
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        blockers.append(f"{blocker_prefix}_artifact_sha256_missing")
        return None
    relative = Path(artifact_path)
    if relative.is_absolute() or ".." in relative.parts:
        blockers.append(f"{blocker_prefix}_artifact_path_unsafe")
        return None
    artifact = bundle_root / relative
    if artifact.is_symlink() or not artifact.is_file():
        blockers.append(f"{blocker_prefix}_artifact_missing")
        return None
    try:
        raw = artifact.read_bytes()
    except OSError:
        blockers.append(f"{blocker_prefix}_artifact_missing")
        return None
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        blockers.append(f"{blocker_prefix}_artifact_sha256_mismatch")
        return None
    return _json_object(artifact, f"{blocker_prefix}_artifact_invalid", blockers)


def _remote_url(repo_root: Path, remote: str) -> str:
    process = _run_git(repo_root, "remote", "get-url", remote)
    if process.returncode == 0 and process.stdout.strip():
        return process.stdout.strip()
    return remote


def _clone_remote_master(repo_root: Path, remote: str, branch: str, target: Path) -> Path:
    process = subprocess.run(
        [
            "git",
            "clone",
            "--no-local",
            "--branch",
            branch,
            "--single-branch",
            _remote_url(repo_root, remote),
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError("promotion_audit_remote_clone_failed")
    return target


def _identity_or_blocker(
    root: Path,
    *,
    blocker: str,
    blockers: list[str],
) -> OfficialBaselineIdentity | None:
    try:
        return assert_official_checkout_matches_active_material(root)
    except (OSError, OfficialBaselineIdentityError):
        blockers.append(blocker)
        return None


def _check_zero_count(
    payload: dict[str, Any] | None,
    field: str,
    blockers: list[str],
) -> int | None:
    if payload is None or field not in payload or not isinstance(payload[field], int):
        blockers.append(f"production_{field}_missing")
        return None
    value = int(payload[field])
    if value != 0:
        blockers.append(f"production_{field}_nonzero")
    return value


def _inspect_launchd_plists(
    launchd_install_dir: Path,
    production_root: Path,
    blockers: list[str],
) -> int:
    valid_labels: set[str] = set()
    for name in PRODUCTION_PLIST_NAMES:
        path = launchd_install_dir / name
        if path.is_symlink() or not path.is_file():
            blockers.append(f"production_launchd_plist_missing:{name}")
            continue
        try:
            with path.open("rb") as handle:
                payload = plistlib.load(handle)
        except (OSError, plistlib.InvalidFileException):
            blockers.append(f"production_launchd_plist_invalid:{name}")
            continue
        expected_label = name.removesuffix(".plist")
        if payload.get("Label") != expected_label:
            blockers.append(f"production_launchd_label_mismatch:{name}")
        elif payload.get("WorkingDirectory") != str(production_root):
            blockers.append(f"production_launchd_working_directory_mismatch:{name}")
        else:
            valid_labels.add(expected_label)
    return len(valid_labels)


def audit_official_promotion_closure(
    *,
    repo_root: Path,
    production_root: Path,
    production_state_root: Path,
    remote: str,
    branch: str,
    expected_release_id: str,
    launchd_install_dir: Path | None = None,
) -> dict[str, object]:
    """Read only the Git and production evidence needed to prove one promotion."""

    blockers: list[str] = []
    remote_identity: OfficialBaselineIdentity | None = None
    remote_master_sha = ""
    ahead_behind: list[int] | None = None
    with tempfile.TemporaryDirectory(prefix="official-promotion-audit-") as temporary:
        clone = Path(temporary) / "master"
        try:
            _clone_remote_master(repo_root, remote, branch, clone)
            remote_master_sha = _git_value(clone, "rev-parse", "HEAD")
            remote_identity = _identity_or_blocker(
                clone,
                blocker="remote_master_identity_invalid",
                blockers=blockers,
            )
            counts = _git_value(
                clone,
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...origin/{branch}",
            ).split()
            if len(counts) == 2 and all(item.isdigit() for item in counts):
                ahead_behind = [int(counts[0]), int(counts[1])]
            else:
                blockers.append("remote_master_ahead_behind_invalid")
        except RuntimeError as exc:
            blockers.append(str(exc))

    production_identity = _identity_or_blocker(
        production_root,
        blocker="production_identity_invalid",
        blockers=blockers,
    )
    try:
        production_source_commit = _git_value(production_root, "rev-parse", "HEAD")
    except RuntimeError as exc:
        blockers.append(str(exc))
        production_source_commit = ""

    if remote_identity is not None:
        if remote_identity.material_release_id != expected_release_id:
            blockers.append("remote_material_release_mismatch")
    if production_identity is not None:
        if production_identity.material_release_id != expected_release_id:
            blockers.append("production_material_release_mismatch")
    if remote_identity is not None and production_identity is not None:
        comparisons = (
            ("strategy_version", "production_strategy_version_mismatch"),
            ("ruleset_version", "production_ruleset_mismatch"),
            ("source_commit", "production_material_source_commit_mismatch"),
            ("material_release_id", "production_material_release_mismatch"),
            ("release_commit", "production_release_commit_mismatch"),
            ("manifest_sha256", "production_material_manifest_mismatch"),
        )
        for field, blocker in comparisons:
            if getattr(remote_identity, field) != getattr(production_identity, field):
                blockers.append(blocker)
    if remote_master_sha and production_source_commit != remote_master_sha:
        blockers.append("production_source_commit_not_remote_master")

    release_manifest = _json_object(
        production_state_root / "release-manifest.json",
        "production_release_manifest_missing",
        blockers,
    )
    qualification = _json_object(
        production_state_root / "qualification-bundle/qualification.json",
        "production_qualification_missing",
        blockers,
    )
    qualification_root = production_state_root / "qualification-bundle"
    selected_suite = _referenced_json_object(
        qualification_root,
        qualification,
        "selected_suite_aggregate",
        blockers,
    )
    formal_ctp = _referenced_json_object(
        qualification_root,
        qualification,
        "formal_ctp_readonly",
        blockers,
    )
    independent_review = _referenced_json_object(
        qualification_root,
        qualification,
        "review",
        blockers,
    )
    activation = _json_object(
        production_state_root / "activation/latest.json",
        "production_activation_audit_missing",
        blockers,
    )
    receipt = _json_object(
        production_state_root / "runtime/state/activation_receipt.json",
        "production_activation_receipt_missing",
        blockers,
    )

    if qualification is not None:
        if qualification.get("evidence_kind") != "stage179_c9_15w_production_qualification":
            blockers.append("production_qualification_not_passed")
        evidence_sha256 = qualification.get("evidence_sha256")
        if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64:
            blockers.append("production_qualification_evidence_missing")
    if selected_suite is not None:
        if selected_suite.get("status") != "passed" or selected_suite.get("failed_count") != 0:
            blockers.append("production_qualification_not_passed")
    if formal_ctp is not None and formal_ctp.get("status") != "qualified":
        blockers.append("production_qualification_not_passed")
    if independent_review is not None:
        for severity in ("p0_count", "p1_count", "p2_count"):
            if independent_review.get(severity) != 0:
                blockers.append(f"production_review_{severity}_nonzero")
    for name, payload in (
        ("release_manifest", release_manifest),
        ("qualification", qualification),
        ("activation", activation),
        ("selected_suite", selected_suite),
        ("formal_ctp", formal_ctp),
        ("independent_review", independent_review),
    ):
        if payload is not None and payload.get("source_commit") != production_source_commit:
            blockers.append(f"production_{name}_source_commit_mismatch")

    manifest_values = [
        payload.get("manifest_sha256")
        for payload in (release_manifest, activation, receipt)
        if payload is not None
    ]
    if len(manifest_values) != 3 or any(not isinstance(item, str) for item in manifest_values):
        blockers.append("production_manifest_sha_evidence_missing")
        production_manifest_sha = ""
    else:
        production_manifest_sha = str(manifest_values[0])
        if len(set(manifest_values)) != 1:
            blockers.append("production_manifest_sha_mismatch")
    if receipt is not None and receipt.get("policy_decision") != "approved":
        blockers.append("production_activation_receipt_not_approved")

    order_count = _check_zero_count(activation, "order_api_called_count", blockers)
    send_count = _check_zero_count(activation, "send_order_api_called_count", blockers)
    cancel_count = _check_zero_count(activation, "cancel_order_api_called_count", blockers)
    qualification_order = _check_zero_count(
        formal_ctp,
        "order_api_called_count",
        blockers,
    )
    qualification_send = _check_zero_count(
        formal_ctp,
        "send_order_api_called_count",
        blockers,
    )
    qualification_cancel = _check_zero_count(
        formal_ctp,
        "cancel_order_api_called_count",
        blockers,
    )
    if qualification_order != order_count:
        blockers.append("production_order_api_count_evidence_mismatch")
    if qualification_cancel != cancel_count:
        blockers.append("production_cancel_order_api_count_evidence_mismatch")
    if qualification_send != send_count:
        blockers.append("production_send_order_api_count_evidence_mismatch")

    conflict_count: int | None = None
    if activation is None or not isinstance(
        activation.get("launchd_surface_conflict_loaded_count"),
        int,
    ):
        blockers.append("production_launchd_conflict_count_missing")
    else:
        conflict_count = int(activation["launchd_surface_conflict_loaded_count"])
        if conflict_count != 0:
            blockers.append("production_launchd_conflict_count_nonzero")
    launchd_label_count = _inspect_launchd_plists(
        launchd_install_dir or Path.home() / "Library/LaunchAgents",
        production_root,
        blockers,
    )
    if launchd_label_count != len(PRODUCTION_PLIST_NAMES):
        blockers.append("production_launchd_label_count_mismatch")

    unique_blockers = sorted(set(blockers))
    return {
        "status": "passed" if not unique_blockers else "fail_closed",
        "blockers": unique_blockers,
        "strategy_version": remote_identity.strategy_version if remote_identity else "",
        "ruleset_version": remote_identity.ruleset_version if remote_identity else "",
        "source_commit": remote_identity.source_commit if remote_identity else "",
        "material_release_id": (
            remote_identity.material_release_id if remote_identity else ""
        ),
        "remote_master_sha": remote_master_sha,
        "production_source_commit": production_source_commit,
        "production_ruleset_version": (
            production_identity.ruleset_version if production_identity else ""
        ),
        "production_material_release_id": (
            production_identity.material_release_id if production_identity else ""
        ),
        "material_manifest_sha256": (
            remote_identity.manifest_sha256 if remote_identity else ""
        ),
        "production_manifest_sha256": production_manifest_sha,
        "ahead_behind": ahead_behind,
        "launchd_label_count": launchd_label_count,
        "conflict_count": conflict_count,
        "order_api_called_count": order_count,
        "send_order_api_called_count": send_count,
        "cancel_order_api_called_count": cancel_count,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit official promotion closure")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--production-root", required=True)
    parser.add_argument("--production-state-root", required=True)
    parser.add_argument("--launchd-install-dir")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="master")
    parser.add_argument("--expected-release-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = audit_official_promotion_closure(
        repo_root=Path(args.repo_root).resolve(strict=True),
        production_root=Path(args.production_root).resolve(strict=True),
        production_state_root=Path(args.production_state_root).resolve(strict=True),
        launchd_install_dir=(
            Path(args.launchd_install_dir).resolve(strict=True)
            if args.launchd_install_dir
            else None
        ),
        remote=args.remote,
        branch=args.branch,
        expected_release_id=args.expected_release_id,
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
