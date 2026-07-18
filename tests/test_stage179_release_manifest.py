from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_stage179_release_manifest as builder
import build_qmt_roll_stage179_rollback_guard as rollback_guard
from build_qmt_roll_stage179_release_manifest import build_release_manifest_file
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    build_release_manifest,
    load_and_validate_release_manifest,
    release_manifest_digest,
    write_release_manifest,
)


class Stage179ReleaseManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name) / "repo"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "stage179@example.invalid")
        self._git("config", "user.name", "Stage179 Test")
        (self.repo / "a.py").write_text("A = 1\n", encoding="utf-8")
        (self.repo / "b.json").write_text('{"b":1}\n', encoding="utf-8")
        self._git("add", "a.py", "b.json")
        self._git("commit", "-m", "base")
        self.commit = self._git("rev-parse", "HEAD").stdout.strip()
        self.manifest_path = Path(self.tempdir.name) / "release.json"

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def payload(self) -> dict[str, object]:
        return build_release_manifest(
            repo_root=self.repo,
            release_id="stage179-test-release",
            execution_profile="stage372-20w",
            official_version="official-v",
            capital=200_000,
            capital_label="20w",
            strategy_semantics_qualification={
                "status": "blocked",
                "evidence_id": "stage372-source-inputs-not-reproducible",
            },
            source_commit=self.commit,
            critical_files=("a.py", "b.json"),
            allowed_runtime_profiles=(
                "offline",
                "production-readonly",
            ),
            created_at_utc="2026-07-18T11:00:00Z",
            ledger_schema_version=1,
            intent_fingerprint_versions=(1, 2),
            reader_capabilities=("intent_fingerprint_v2",),
        )

    def test_default_manifest_covers_runtime_and_deployment_boundary(self) -> None:
        required = {
            "examples/portfolio_backtesting/qmt_roll_official_live_tick_journal.py",
            "examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py",
            "examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py",
            "examples/portfolio_backtesting/audit_qmt_roll_stage179_readonly_canary_qualification.py",
            "examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py",
            "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py",
            "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh",
            "examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-direct.plist",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-supervisor.plist",
            "tests/stage179_performance_gate.py",
            "tests/test_stage179_performance_gate_diagnostics.py",
            "tests/test_stage179_readonly_canary_qualification.py",
            "tests/test_stage608_continuous_tick_stream.py",
            "tests/test_stage930_fast_lane.py",
        }

        self.assertTrue(required.issubset(set(builder.DEFAULT_CRITICAL_FILES)))

    def validate(self, path: Path | None = None, *, profile: str = "offline") -> dict[str, object]:
        return load_and_validate_release_manifest(
            path or self.manifest_path,
            repo_root=self.repo,
            expected_official_version="official-v",
            expected_capital=200_000,
            expected_capital_label="20w",
            expected_execution_profile="stage372-20w",
            required_runtime_profile=profile,
            current_commit=self._git("rev-parse", "HEAD").stdout.strip(),
            required_reader_capabilities=("intent_fingerprint_v2",),
        )

    def write(self, payload: dict[str, object], name: str = "release.json") -> Path:
        path = Path(self.tempdir.name) / name
        write_release_manifest(path, payload)
        return path

    def reseal(self, payload: dict[str, object]) -> dict[str, object]:
        payload["manifest_sha256"] = release_manifest_digest(payload)
        return payload

    def test_valid_manifest_checks_exact_bytes_and_allows_ancestor_commit(self) -> None:
        write_release_manifest(self.manifest_path, self.payload())
        (self.repo / "later.txt").write_text("later\n", encoding="utf-8")
        self._git("add", "later.txt")
        self._git("commit", "-m", "later")

        loaded = self.validate()

        self.assertEqual("stage179-test-release", loaded["release_id"])
        self.assertEqual(self.commit, loaded["source_commit"])

    def test_manifest_rejects_execution_profile_mismatch(self) -> None:
        write_release_manifest(self.manifest_path, self.payload())

        with self.assertRaisesRegex(
            ReleaseManifestError,
            "release_manifest_execution_profile_mismatch",
        ):
            load_and_validate_release_manifest(
                self.manifest_path,
                repo_root=self.repo,
                expected_official_version="official-v",
                expected_capital=200_000,
                expected_capital_label="20w",
                expected_execution_profile="c9-15w-historical",
                required_runtime_profile="offline",
                current_commit=self._git("rev-parse", "HEAD").stdout.strip(),
            )

    def test_blocked_strategy_semantics_allows_readonly_but_not_submit_profiles(self) -> None:
        payload = self.payload()
        payload["strategy_semantics_qualification"] = {
            "status": "blocked",
            "evidence_id": "stage372-source-inputs-not-reproducible",
        }
        payload["allowed_runtime_profiles"] = [
            "offline",
            "production-readonly",
            "simnow",
        ]
        self.reseal(payload)
        write_release_manifest(self.manifest_path, payload)

        self.validate(profile="production-readonly")
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "release_manifest_strategy_semantics_unqualified",
        ):
            self.validate(profile="simnow")

    def test_stage372_self_declared_passed_manifest_is_rejected(self) -> None:
        payload = self.payload()
        payload["strategy_semantics_qualification"] = {
            "status": "passed",
            "evidence_id": "anything-the-caller-wants",
        }
        payload["allowed_runtime_profiles"] = ["offline", "simnow"]
        self.reseal(payload)
        write_release_manifest(self.manifest_path, payload)

        with self.assertRaisesRegex(
            ReleaseManifestError,
            "release_manifest_stage372_semantics_promotion_unsupported",
        ):
            self.validate(profile="simnow")

    def test_manifest_rejects_digest_version_capital_profile_or_capability_tamper(self) -> None:
        base = self.payload()
        mutations: list[tuple[str, dict[str, object], str]] = []
        version = copy.deepcopy(base)
        version["official_version"] = "wrong-v"
        mutations.append(("version", self.reseal(version), "offline"))
        capital = copy.deepcopy(base)
        capital["capital"] = 150_000
        mutations.append(("capital", self.reseal(capital), "offline"))
        profile = copy.deepcopy(base)
        profile["allowed_runtime_profiles"] = ["production-readonly"]
        mutations.append(("profile", self.reseal(profile), "offline"))
        capability = copy.deepcopy(base)
        capability["ledger_contract"]["reader_capabilities"] = []
        mutations.append(("capability", self.reseal(capability), "offline"))
        digest = copy.deepcopy(base)
        digest["manifest_sha256"] = "0" * 64
        mutations.append(("digest", digest, "offline"))
        critical = copy.deepcopy(base)
        critical["critical_files"][0]["sha256"] = "f" * 64
        mutations.append(("critical", self.reseal(critical), "offline"))

        for name, mutation, required_profile in mutations:
            with self.subTest(name=name):
                path = self.write(mutation, f"{name}.json")
                with self.assertRaises(ReleaseManifestError):
                    self.validate(path, profile=required_profile)

    def test_manifest_rejects_critical_file_byte_change(self) -> None:
        write_release_manifest(self.manifest_path, self.payload())
        (self.repo / "a.py").write_text("A = 2\n", encoding="utf-8")

        with self.assertRaises(ReleaseManifestError):
            self.validate()

    def test_manifest_rejects_non_ancestor_or_missing_source_commit(self) -> None:
        payload = self.payload()
        payload["source_commit"] = "f" * 40
        self.reseal(payload)
        write_release_manifest(self.manifest_path, payload)

        with self.assertRaises(ReleaseManifestError):
            self.validate()

    def test_manifest_rejects_resealed_invalid_structure(self) -> None:
        mutations: list[dict[str, object]] = []
        empty_release = copy.deepcopy(self.payload())
        empty_release["release_id"] = ""
        mutations.append(self.reseal(empty_release))
        unknown_profile = copy.deepcopy(self.payload())
        unknown_profile["allowed_runtime_profiles"] = ["offline", "unknown"]
        mutations.append(self.reseal(unknown_profile))
        malformed_critical = copy.deepcopy(self.payload())
        malformed_critical["critical_files"] = ["a.py"]
        mutations.append(self.reseal(malformed_critical))

        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                path = self.write(mutation, f"invalid-structure-{index}.json")
                with self.assertRaises(ReleaseManifestError):
                    self.validate(path)

    def test_ledger_rollback_safety_requires_v2_reader_after_side_effect(self) -> None:
        no_v2 = rollback_guard.inspect_ledger_rollback_safety(
            [{"event_type": "reserved", "intent_fingerprint_version": 1}]
        )
        reservation_only = rollback_guard.inspect_ledger_rollback_safety(
            [
                {
                    "event_type": "reserved",
                    "intent_fingerprint_version": 2,
                    "spool_lease_owner": "service-1",
                    "spool_lease_token": "lease-1",
                },
                {
                    "event_type": "spool_crash_recovery_pre_send_safe_terminal",
                    "intent_fingerprint_version": 2,
                    "spool_lease_owner": "service-1",
                    "spool_lease_token": "lease-1",
                },
            ]
        )
        side_effect = rollback_guard.inspect_ledger_rollback_safety(
            [
                {
                    "event_type": "api_slot_reserved",
                    "intent_fingerprint_version": 2,
                    "api_slot_type": "send_order",
                }
            ]
        )

        self.assertEqual("v1_code_and_plist_rollback_allowed", no_v2.disposition)
        self.assertEqual(
            "broker_snapshot_required_keep_v2_reader",
            reservation_only.disposition,
        )
        self.assertEqual(
            "v2_reader_required_reconcile_and_roll_forward",
            side_effect.disposition,
        )

    def test_rollback_cli_is_readonly_and_writes_separate_evidence(self) -> None:
        ledger_path = Path(self.tempdir.name) / "ledger.ndjson"
        original = (
            json.dumps(
                {
                    "event_type": "api_slot_reserved",
                    "intent_fingerprint_version": 2,
                    "api_slot_type": "send_order",
                }
            )
            + "\n"
        ).encode()
        ledger_path.write_bytes(original)
        json_output = Path(self.tempdir.name) / "rollback.json"
        markdown_output = Path(self.tempdir.name) / "rollback.md"

        with patch("sys.stdout"):
            rollback_guard.main(
                [
                    "--ledger",
                    str(ledger_path),
                    "--json-output",
                    str(json_output),
                    "--markdown-output",
                    str(markdown_output),
                ]
            )

        self.assertEqual(original, ledger_path.read_bytes())
        self.assertEqual(
            "v2_reader_required_reconcile_and_roll_forward",
            json.loads(json_output.read_text(encoding="utf-8"))["disposition"],
        )
        self.assertIn("只读 ledger", markdown_output.read_text(encoding="utf-8"))

    def test_builder_requires_clean_tree_and_refuses_different_overwrite(self) -> None:
        output = Path(self.tempdir.name) / "built-release.json"
        dirty = self.repo / "dirty.txt"
        dirty.write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(ReleaseManifestError):
            build_release_manifest_file(
                output_path=output,
                repo_root=self.repo,
                release_id="r1",
                official_version="official-v",
                capital=200_000,
                capital_label="20w",
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline",),
                created_at_utc="2026-07-18T11:00:00Z",
            )
        dirty.unlink()

        first = build_release_manifest_file(
            output_path=output,
            repo_root=self.repo,
            release_id="r1",
            official_version="official-v",
            capital=200_000,
            capital_label="20w",
            critical_files=("a.py", "b.json"),
            allowed_runtime_profiles=("offline",),
            created_at_utc="2026-07-18T11:00:00Z",
        )
        same = build_release_manifest_file(
            output_path=output,
            repo_root=self.repo,
            release_id="r1",
            official_version="official-v",
            capital=200_000,
            capital_label="20w",
            critical_files=("a.py", "b.json"),
            allowed_runtime_profiles=("offline",),
            created_at_utc="2026-07-18T11:00:00Z",
        )
        self.assertEqual(first, same)
        self.assertEqual(
            set(builder.EXECUTION_LEDGER_READER_CAPABILITIES),
            set(first["ledger_contract"]["reader_capabilities"]),
        )
        with self.assertRaises(ReleaseManifestError):
            build_release_manifest_file(
                output_path=output,
                repo_root=self.repo,
                release_id="r2",
                official_version="official-v",
                capital=200_000,
                capital_label="20w",
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline",),
                created_at_utc="2026-07-18T11:00:00Z",
            )

    def test_builder_refuses_stage372_submit_even_with_self_declared_pass(self) -> None:
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "release_builder_stage372_semantics_promotion_unsupported",
        ):
            build_release_manifest_file(
                output_path=Path(self.tempdir.name) / "unsafe-release.json",
                repo_root=self.repo,
                release_id="unsafe",
                execution_profile="stage372-20w",
                official_version="official-v",
                capital=200_000,
                capital_label="20w",
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline", "simnow"),
                strategy_semantics_qualification={
                    "status": "passed",
                    "evidence_id": "caller-self-declared",
                },
                created_at_utc="2026-07-18T11:00:00Z",
            )

    def test_builder_rejects_transient_worktree_bytes_not_in_source_commit(self) -> None:
        original_build = builder.build_release_manifest

        def race_build(**kwargs: object) -> dict[str, object]:
            path = self.repo / "a.py"
            original = path.read_bytes()
            path.write_text("A = 999\n", encoding="utf-8")
            try:
                return original_build(**kwargs)
            finally:
                path.write_bytes(original)

        with patch.object(builder, "build_release_manifest", side_effect=race_build):
            with self.assertRaises(ReleaseManifestError):
                build_release_manifest_file(
                    output_path=Path(self.tempdir.name) / "race-release.json",
                    repo_root=self.repo,
                    release_id="race",
                    official_version="official-v",
                    capital=200_000,
                    capital_label="20w",
                    critical_files=("a.py", "b.json"),
                    allowed_runtime_profiles=("offline",),
                    created_at_utc="2026-07-18T11:00:00Z",
                )

    def test_default_manifest_covers_builder_launcher_and_submit_adapter(self) -> None:
        defaults = set(builder.DEFAULT_CRITICAL_FILES)
        self.assertIn(
            "examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/provision_qmt_roll_stage372_launchd_directories.py",
            defaults,
        )
        for stage in ("902", "903", "904", "905", "927"):
            self.assertTrue(
                any(f"stage{stage}_" in path for path in defaults),
                stage,
            )


if __name__ == "__main__":
    unittest.main()
