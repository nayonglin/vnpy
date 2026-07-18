from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess

from qmt_roll_official_live_execution_ledger import (
    EXECUTION_LEDGER_READER_CAPABILITIES,
    INTENT_FINGERPRINT_VERSION_V2,
    LEDGER_SCHEMA_VERSION,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    build_release_manifest,
    serialize_release_manifest,
    write_release_manifest,
)
from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
DEFAULT_CRITICAL_FILES = (
    "examples/portfolio_backtesting/qmt_roll_official_live_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_c9_intraday_state.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_intent_spool.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_runtime_profile.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_release_manifest.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_journal.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_reader.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_recovery.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_types.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_time.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_trace.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage179_rollback_guard.py",
    "examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py",
    "examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py",
    "examples/portfolio_backtesting/run_qmt_alignment_backtest.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage927_official_live_real_submit_arming_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_owned_child_guard.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_supervisor_child.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage941_official_live_c9_detector.py",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-direct.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-supervisor.plist",
)


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseManifestError(
            f"release_builder_git_failed:{' '.join(args)}:{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_blob(repo_root: Path, source_commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{source_commit}:{path}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseManifestError(
            f"release_builder_critical_file_not_in_source_commit:{path}"
        )
    return result.stdout


def _assert_clean_source_tree(repo_root: Path, source_commit: str) -> None:
    if _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}") != source_commit:
        raise ReleaseManifestError("release_builder_head_changed_during_build")
    if _git(repo_root, "status", "--porcelain", "--untracked-files=all"):
        raise ReleaseManifestError("release_builder_tree_changed_during_build")


def _assert_manifest_matches_source_commit(
    repo_root: Path,
    source_commit: str,
    payload: dict[str, object],
) -> None:
    rows = payload.get("critical_files")
    if not isinstance(rows, list):
        raise ReleaseManifestError("release_builder_critical_files_invalid")
    for row in rows:
        if not isinstance(row, dict):
            raise ReleaseManifestError("release_builder_critical_files_invalid")
        path = str(row.get("path", ""))
        blob = _git_blob(repo_root, source_commit, path)
        if (
            row.get("size_bytes") != len(blob)
            or row.get("sha256") != hashlib.sha256(blob).hexdigest()
        ):
            raise ReleaseManifestError(
                f"release_builder_worktree_source_mismatch:{path}"
            )


def build_release_manifest_file(
    *,
    output_path: Path | str,
    repo_root: Path | str = REPO_ROOT,
    release_id: str,
    official_version: str | None = None,
    capital: int | float | None = None,
    capital_label: str | None = None,
    critical_files: Iterable[str | Path] = DEFAULT_CRITICAL_FILES,
    allowed_runtime_profiles: Iterable[str | ExecutionRuntimeProfile] = tuple(
        ExecutionRuntimeProfile
    ),
    created_at_utc: str | None = None,
) -> dict[str, object]:
    if official_version is None or capital is None or capital_label is None:
        # CLI convenience only. Tests and release automation should pass the
        # identity explicitly so importing this builder stays side-effect free.
        from qmt_roll_official_live_config import (
            OFFICIAL_LIVE_CAPITAL,
            OFFICIAL_LIVE_CAPITAL_LABEL,
            OFFICIAL_LIVE_VERSION,
        )

        official_version = official_version or OFFICIAL_LIVE_VERSION
        capital = OFFICIAL_LIVE_CAPITAL if capital is None else capital
        capital_label = capital_label or OFFICIAL_LIVE_CAPITAL_LABEL
    repo = Path(repo_root).expanduser().resolve(strict=True)
    dirty = _git(repo, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise ReleaseManifestError("release_builder_requires_clean_tree")
    source_commit = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    created = created_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    payload = build_release_manifest(
        repo_root=repo,
        release_id=release_id,
        official_version=official_version,
        capital=capital,
        capital_label=capital_label,
        source_commit=source_commit,
        critical_files=critical_files,
        allowed_runtime_profiles=allowed_runtime_profiles,
        created_at_utc=created,
        ledger_schema_version=LEDGER_SCHEMA_VERSION,
        intent_fingerprint_versions=(1, INTENT_FINGERPRINT_VERSION_V2),
        reader_capabilities=tuple(sorted(EXECUTION_LEDGER_READER_CAPABILITIES)),
    )
    _assert_manifest_matches_source_commit(repo, source_commit, payload)
    _assert_clean_source_tree(repo, source_commit)
    destination = Path(output_path)
    if destination.exists():
        try:
            existing = destination.read_bytes()
        except OSError as exc:
            raise ReleaseManifestError(
                f"release_builder_existing_read_failed:{exc}"
            ) from exc
        expected = serialize_release_manifest(payload)
        if existing != expected:
            raise ReleaseManifestError(
                "release_builder_refuses_different_overwrite"
            )
        return payload
    write_release_manifest(destination, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an immutable Stage179 release manifest from a clean tree."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--critical-file", action="append", default=[])
    args = parser.parse_args()
    payload = build_release_manifest_file(
        output_path=args.output,
        release_id=args.release_id,
        critical_files=args.critical_file or DEFAULT_CRITICAL_FILES,
    )
    print(payload["manifest_sha256"])


if __name__ == "__main__":
    main()
