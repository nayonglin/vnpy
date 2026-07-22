from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import install_qmt_roll_stage948_official_live_production as installer  # noqa: E402


class Stage948ProductionInstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name).resolve()
        self.main = root / "main"
        self.stable = root / "stable"
        self.state = root / "state"
        self.launchd = root / "LaunchAgents"
        for repo in (self.main, self.stable):
            (repo / "examples/portfolio_backtesting").mkdir(parents=True)

        venv = self.main / ".py311"
        (venv / "bin").mkdir(parents=True)
        python = venv / "bin/python3.11"
        python.write_bytes(b"test-python")
        python.chmod(0o775)
        (venv / "bin/python").symlink_to("python3.11")
        formal = venv / "lib/python3.11/site-packages/vnpy_ctp/api/libs"
        formal.mkdir(parents=True)
        for name in (
            "thostmduserapi_se.framework",
            "thosttraderapi_se.framework",
        ):
            (formal / name).mkdir()

        data = self.main / "examples/portfolio_backtesting/backtest_outputs"
        data.mkdir(mode=0o700)
        for name in ("ctp_live.local.env", "official_live_email.local.env"):
            source = self.main / "examples/portfolio_backtesting" / name
            source.write_text("TEST_CONFIGURED=1\n", encoding="utf-8")
            source.chmod(0o600)
        trader = self.main / ".vntrader"
        trader.mkdir()
        settings = trader / "vt_setting.json"
        settings.write_text(
            json.dumps(
                {
                    "datafeed.username": "configured-user",
                    "datafeed.password": "configured-password",
                }
            ),
            encoding="utf-8",
        )
        settings.chmod(0o644)
        database = trader / "database.db"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "CREATE TABLE dbbardata (datetime TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO dbbardata(datetime) VALUES "
                "('2026-07-21 00:00:00')"
            )
            connection.commit()
        finally:
            connection.close()
        database.chmod(0o644)

        (self.stable / ".gitignore").write_text(
            (ROOT / ".gitignore").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        stable_launchd = (
            self.stable / "examples/portfolio_backtesting/launchd"
        )
        stable_launchd.mkdir()
        for name in installer.PRODUCTION_PLIST_NAMES:
            (stable_launchd / name).write_bytes(
                (PORTFOLIO_DIR / "launchd" / name).read_bytes()
            )
        subprocess.run(["git", "init", "--quiet"], cwd=self.stable, check=True)
        subprocess.run(
            ["git", "add", ".gitignore", "examples"],
            cwd=self.stable,
            check=True,
        )
        self._commit_stable("stable baseline")
        self.paths = installer.ProductionInstallPaths(
            main_repo=self.main,
            stable_repo=self.stable,
            state_root=self.state,
            launchd_install_dir=self.launchd,
        )

    def _commit_stable(self, message: str) -> None:
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=stage948-test",
                "-c",
                "user.email=stage948-test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                message,
            ],
            cwd=self.stable,
            check=True,
        )

    def _head(self) -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.stable,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()

    def _old_production_plist(self, label: str, version: str = "old") -> bytes:
        return installer.plistlib.dumps(
            {
                "Label": label,
                "ProgramArguments": [f"/{version}/production"],
                "Umask": "077",
                "Version": version,
            }
        )

    def _write_launchagent(self, label: str, payload: bytes) -> Path:
        self.launchd.mkdir(mode=0o700, exist_ok=True)
        path = self.launchd / f"{label}.plist"
        path.write_bytes(payload)
        path.chmod(0o600)
        return path

    def _write_conflict_plist(self, label: str) -> tuple[Path, bytes]:
        payload = installer.plistlib.dumps(
            {"Label": label, "ProgramArguments": ["/legacy/job"]}
        )
        return self._write_launchagent(label, payload), payload

    def _activation_fixture(self) -> tuple[tuple[str, ...], dict[str, object]]:
        installer.provision_stable_assets(self.paths)
        labels = installer._production_labels_from_plists(self.paths)
        return labels, {
            "source_commit": self._head(),
            "manifest_sha256": "b" * 64,
        }

    class _FakeLaunchctl:
        def __init__(
            self,
            *,
            loaded: set[str] | None = None,
            running: set[str] | None = None,
            loaded_payloads: dict[str, bytes] | None = None,
            bootstrap_failures: dict[str, str] | None = None,
            bootout_failures: dict[str, str] | None = None,
            late_load_after_preflight: set[str] | None = None,
            inject_labels_at_domain_print: dict[int, set[str]] | None = None,
        ) -> None:
            self.loaded = set(loaded or set())
            self.running = set(running or set())
            self.loaded_payloads = dict(loaded_payloads or {})
            self.bootstrap_failures = dict(bootstrap_failures or {})
            self.bootout_failures = dict(bootout_failures or {})
            self.late_load_after_preflight = set(
                late_load_after_preflight or set()
            )
            self.late_loaded: set[str] = set()
            self.inject_labels_at_domain_print = {
                index: set(labels)
                for index, labels in (
                    inject_labels_at_domain_print or {}
                ).items()
            }
            self.domain_print_count = 0
            self.calls: list[list[str]] = []

        def __call__(
            self, command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            self.calls.append(list(command))
            action = command[1]
            target = command[2]
            if action == "print" and target.count("/") == 1:
                self.domain_print_count += 1
                self.loaded.update(
                    self.inject_labels_at_domain_print.get(
                        self.domain_print_count,
                        set(),
                    )
                )
                rows = "\n".join(
                    f"\t\t0 - {label}"
                    for label in sorted(self.loaded)
                )
                return subprocess.CompletedProcess(
                    command,
                    0,
                    (
                        f"{target} = {{\n"
                        "\tservices = {\n"
                        f"{rows}\n"
                        "\t}\n"
                        "}\n"
                    ),
                    "",
                )
            if action == "print":
                label = target.split("/", 2)[-1]
                if label not in self.loaded:
                    if (
                        label in self.late_load_after_preflight
                        and label not in self.late_loaded
                    ):
                        self.loaded.add(label)
                        self.late_loaded.add(label)
                    uid = target.split("/", 2)[1]
                    return subprocess.CompletedProcess(
                        command,
                        113,
                        (
                            "Bad request.\n"
                            f'Could not find service "{label}" in domain '
                            f"for user gui: {uid}\n"
                        ),
                        "",
                    )
                state = "running" if label in self.running else "exited"
                pid = "\tpid = 777\n" if label in self.running else ""
                return subprocess.CompletedProcess(
                    command,
                    0,
                    (
                        f"{target} = {{\n"
                        f"\tstate = {state}\n"
                        f"{pid}"
                        "}\n"
                    ),
                    "",
                )
            if action == "bootout":
                label = target.split("/", 2)[-1]
                # Model the ambiguous C API boundary: the side effect can be
                # committed even when the wrapper returns an error or times out.
                self.loaded.discard(label)
                self.running.discard(label)
                self.loaded_payloads.pop(label, None)
                failure = self.bootout_failures.get(label, "")
                if failure == "return5_after_remove":
                    return subprocess.CompletedProcess(
                        command, 5, "failed after remove\n", ""
                    )
                if failure == "timeout_after_remove":
                    raise subprocess.TimeoutExpired(command, 10)
                return subprocess.CompletedProcess(command, 0, "", "")
            if action == "bootstrap":
                payload_bytes = Path(command[3]).read_bytes()
                payload = installer.plistlib.loads(payload_bytes)
                label = str(payload["Label"])
                failure = self.bootstrap_failures.get(label, "")
                if failure == "return5_before_load":
                    return subprocess.CompletedProcess(
                        command, 5, "failed before load\n", ""
                    )
                self.loaded.add(label)
                self.loaded_payloads[label] = payload_bytes
                if failure == "return5_after_load":
                    return subprocess.CompletedProcess(
                        command, 5, "failed after load\n", ""
                    )
                if failure == "timeout_after_load":
                    raise subprocess.TimeoutExpired(command, 10)
                return subprocess.CompletedProcess(command, 0, "", "")
            raise AssertionError(command)

    def _activate_with_fixture(
        self,
        labels: tuple[str, ...],
        manifest: dict[str, object],
        launchctl: _FakeLaunchctl,
    ) -> dict[str, object]:
        with patch.object(
            installer,
            "_validate_prepared_production_chain",
            return_value=(manifest, labels),
        ):
            return installer.activate_prepared_production(
                self.paths,
                confirmation=installer.PRODUCTION_ACTIVATION_CONFIRM_TEXT,
                launchctl_runner=launchctl,
            )

    def test_prepare_only_stages_private_plists_and_never_writes_launchagents(self) -> None:
        result = installer.provision_stable_assets(self.paths)

        self.assertEqual(
            "production_assets_prepared_not_activated", result["status"]
        )
        self.assertEqual(0, result["launchagents_written_count"])
        self.assertEqual(0, result["launchctl_called_count"])
        self.assertFalse(self.launchd.exists())
        self.assertFalse((self.state / "qualification-bundle").exists())
        manifest = json.loads(
            self.paths.plist_rollback_manifest.read_text(encoding="utf-8")
        )
        self.assertEqual(2, manifest["schema_version"])
        self.assertEqual("prepared", manifest["status"])
        self.assertEqual(set(installer.PRODUCTION_PLIST_NAMES), {
            entry["plist_name"] for entry in manifest["entries"].values()
        })
        for name in installer.PRODUCTION_PLIST_NAMES:
            staged = self.paths.plist_staging_root / name
            source = self.stable / "examples/portfolio_backtesting/launchd" / name
            self.assertEqual(source.read_bytes(), staged.read_bytes())
            self.assertEqual(0o600, staged.stat().st_mode & 0o777)
        for path in (
            self.stable / "examples/portfolio_backtesting/ctp_live.local.env",
            self.stable / "examples/portfolio_backtesting/official_live_email.local.env",
            self.stable / ".vntrader/vt_setting.json",
            self.stable / ".vntrader/database.db",
        ):
            self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_prepare_does_not_replace_existing_launchagent(self) -> None:
        name = installer.PRODUCTION_PLIST_NAMES[0]
        label = name.removesuffix(".plist")
        old_bytes = self._old_production_plist(label)
        destination = self._write_launchagent(label, old_bytes)

        result = installer.provision_stable_assets(self.paths)

        self.assertEqual(old_bytes, destination.read_bytes())
        self.assertEqual(0, result["launchagents_written_count"])
        self.assertEqual(
            (self.stable / "examples/portfolio_backtesting/launchd" / name).read_bytes(),
            (self.paths.plist_staging_root / name).read_bytes(),
        )

    def test_prepared_generation_is_exact_idempotent_and_cross_generation_blocks(self) -> None:
        installer.provision_stable_assets(self.paths)
        before_manifest = self.paths.plist_rollback_manifest.read_bytes()
        before_staged = {
            name: (self.paths.plist_staging_root / name).read_bytes()
            for name in installer.PRODUCTION_PLIST_NAMES
        }
        repeated = installer.provision_stable_assets(self.paths)
        self.assertTrue(
            all(
                status == "staged_unchanged"
                for status in repeated["production_plist_staging_statuses"].values()
            )
        )

        name = installer.PRODUCTION_PLIST_NAMES[0]
        source = self.stable / "examples/portfolio_backtesting/launchd" / name
        payload = installer.plistlib.loads(source.read_bytes())
        payload["Version"] = "different-prepared-generation"
        source.write_bytes(installer.plistlib.dumps(payload))
        subprocess.run(
            ["git", "add", str(source.relative_to(self.stable))],
            cwd=self.stable,
            check=True,
        )
        self._commit_stable("different prepared generation")
        with self.assertRaisesRegex(
            installer.ProductionInstallError,
            "staging_commit_mismatch",
        ):
            installer.provision_stable_assets(self.paths)
        self.assertEqual(before_manifest, self.paths.plist_rollback_manifest.read_bytes())
        self.assertEqual(
            before_staged,
            {
                item: (self.paths.plist_staging_root / item).read_bytes()
                for item in installer.PRODUCTION_PLIST_NAMES
            },
        )

    def test_new_generation_requires_verified_settled_launchagents_disk(self) -> None:
        labels, manifest = self._activation_fixture()
        self._activate_with_fixture(labels, manifest, self._FakeLaunchctl())
        destination = self.launchd / f"{labels[0]}.plist"
        external_bytes = self._old_production_plist(labels[0], "external")
        destination.write_bytes(external_bytes)
        destination.chmod(0o600)
        before_manifest = self.paths.plist_rollback_manifest.read_bytes()

        with self.assertRaisesRegex(
            installer.ProductionInstallError,
            "settled_disk_sha_mismatch",
        ):
            installer.provision_stable_assets(self.paths)

        self.assertEqual(external_bytes, destination.read_bytes())
        self.assertEqual(
            before_manifest,
            self.paths.plist_rollback_manifest.read_bytes(),
        )

    def test_activation_chain_binds_artifacts_and_staging(self) -> None:
        installer.provision_stable_assets(self.paths)
        qualification = self.paths.qualification_evidence
        qualification.parent.mkdir(mode=0o700)
        qualification.write_text("{}\n", encoding="utf-8")
        self.paths.release_manifest.write_text("{}\n", encoding="utf-8")
        self.paths.activation_receipt.write_text("{}\n", encoding="utf-8")
        for path in (
            qualification,
            self.paths.release_manifest,
            self.paths.activation_receipt,
        ):
            path.chmod(0o600)
        manifest = {
            "source_commit": self._head(),
            "manifest_sha256": "b" * 64,
            "created_at_utc": "2026-07-21T00:00:00Z",
            "critical_files": [],
            "strategy_semantics_qualification": {
                "status": "passed",
                "evidence_id": "c" * 64,
            },
        }
        with (
            patch.object(
                installer,
                "load_and_validate_release_manifest",
                return_value=manifest,
            ),
            patch.object(
                installer,
                "load_and_validate_production_qualification_evidence",
                return_value={"evidence_sha256": "c" * 64},
            ),
            patch.object(
                installer,
                "validate_stage179_activation_receipt",
                return_value=(),
            ),
        ):
            observed, labels = installer._validate_prepared_production_chain(
                self.paths
            )
        self.assertEqual(manifest, observed)
        self.assertEqual(7, len(labels))

    def test_activation_success_removes_conflict_disk_and_leaves_exact_seven(self) -> None:
        labels, manifest = self._activation_fixture()
        conflict = installer.CONFLICTING_JOB_LABELS[0]
        conflict_path, _ = self._write_conflict_plist(conflict)
        launchctl = self._FakeLaunchctl(loaded={conflict})

        result = self._activate_with_fixture(labels, manifest, launchctl)

        self.assertEqual(
            "production_launchd_activated_no_ctp_connection",
            result["status"],
        )
        self.assertEqual(set(labels), launchctl.loaded)
        self.assertFalse(conflict_path.exists())
        self.assertEqual(7, result["reboot_surface_production_plist_count"])
        self.assertEqual(0, result["reboot_surface_conflict_plist_count"])
        self.assertTrue(result["post_activation_session_kickstart_required"])
        self.assertEqual(0, result["ctp_connection_attempted_count"])
        self.assertEqual(0, result["order_api_called_count"])
        for label in labels:
            self.assertEqual(
                (self.paths.plist_staging_root / f"{label}.plist").read_bytes(),
                (self.launchd / f"{label}.plist").read_bytes(),
            )

    def test_unknown_unloaded_owned_plist_blocks_before_mutation(self) -> None:
        labels, manifest = self._activation_fixture()
        unknown = "local.qmt-roll.official-live.unregistered-unloaded"
        self._write_launchagent(
            unknown,
            installer.plistlib.dumps(
                {"Label": unknown, "ProgramArguments": ["/unknown/job"]}
            ),
        )
        launchctl = self._FakeLaunchctl()

        with self.assertRaisesRegex(
            installer.ProductionActivationError,
            "owned_surface_unverified",
        ):
            self._activate_with_fixture(labels, manifest, launchctl)

        self.assertFalse(
            any(call[1] in {"bootout", "bootstrap"} for call in launchctl.calls)
        )

    def test_individual_launchctl_result_requires_exact_complete_output(self) -> None:
        uid = installer.os.getuid()
        label = installer.PRODUCTION_PLIST_NAMES[0].removesuffix(".plist")
        loaded = f"gui/{uid}/{label} = {{\n\tstate = exited\n}}\n"
        missing = (
            "Bad request.\n"
            f'Could not find service "{label}" in domain for user gui: {uid}\n'
        )
        self.assertIs(
            True,
            installer.classify_individual_launchctl_result(
                exit_code=0,
                output=loaded,
                label=label,
                uid=uid,
            )[0],
        )
        self.assertIs(
            False,
            installer.classify_individual_launchctl_result(
                exit_code=113,
                output=missing,
                label=label,
                uid=uid,
            )[0],
        )
        for exit_code, output in (
            (0, loaded.removesuffix("}\n")),
            (113, f"Could not find service {label}\n"),
            (5, "unexpected\n"),
        ):
            with self.subTest(exit_code=exit_code, output=output):
                self.assertIsNone(
                    installer.classify_individual_launchctl_result(
                        exit_code=exit_code,
                        output=output,
                        label=label,
                        uid=uid,
                    )[0]
                )

    def test_same_label_service_row_drift_between_d1_d2_is_blocked(self) -> None:
        uid = installer.os.getuid()
        domain = f"gui/{uid}"
        label = installer.PRODUCTION_PLIST_NAMES[0].removesuffix(".plist")
        domain_calls = 0

        def runner(
            command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            nonlocal domain_calls
            target = command[2]
            if target == domain:
                domain_calls += 1
                row = (
                    f"\t\t0 - {label}"
                    if domain_calls == 1
                    else f"\t\t777 (pe) {label}"
                )
                return subprocess.CompletedProcess(
                    command,
                    0,
                    f"{domain} = {{\n\tservices = {{\n{row}\n\t}}\n}}\n",
                    "",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                f"{domain}/{label} = {{\n\tstate = running\n\tpid = 777\n}}\n",
                "",
            )

        report = installer.inspect_owned_launchd_surface(
            launchd_install_dir=Path(self.tempdir.name) / "absent-launchagents",
            allowed_production_labels=(label,),
            known_conflicting_labels=(),
            launchctl_runner=runner,
            uid=uid,
        )

        self.assertEqual("blocked", report["status"])
        self.assertIn("owned_domain_changed_d1_d2", report["blockers"])

    def test_individual_loaded_but_missing_from_both_domains_is_blocked(self) -> None:
        uid = installer.os.getuid()
        domain = f"gui/{uid}"
        label = installer.PRODUCTION_PLIST_NAMES[0].removesuffix(".plist")

        def runner(
            command: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            target = command[2]
            if target == domain:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    f"{domain} = {{\n\tservices = {{\n\t}}\n}}\n",
                    "",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                f"{domain}/{label} = {{\n\tstate = running\n\tpid = 777\n}}\n",
                "",
            )

        report = installer.inspect_owned_launchd_surface(
            launchd_install_dir=Path(self.tempdir.name) / "absent-launchagents",
            allowed_production_labels=(label,),
            known_conflicting_labels=(),
            launchctl_runner=runner,
            uid=uid,
        )

        self.assertEqual("blocked", report["status"])
        self.assertIn("individual_loaded_set_mismatch_d1", report["blockers"])
        self.assertIn("individual_loaded_set_mismatch_d2", report["blockers"])

    def test_external_plist_update_after_journal_is_preserved_by_cas(self) -> None:
        label = installer.PRODUCTION_PLIST_NAMES[0].removesuffix(".plist")
        destination = self._write_launchagent(
            label,
            self._old_production_plist(label, "journaled"),
        )
        labels, manifest = self._activation_fixture()
        external_bytes = self._old_production_plist(label, "external-after-journal")
        original_write = installer._write_activation_audit
        injected = False

        def write_then_inject(
            paths: installer.ProductionInstallPaths,
            audit: dict[str, object],
        ) -> None:
            nonlocal injected
            original_write(paths, audit)
            if audit.get("status") == "activation_in_progress" and not injected:
                injected = True
                destination.write_bytes(external_bytes)
                destination.chmod(0o600)

        with patch.object(
            installer,
            "_write_activation_audit",
            side_effect=write_then_inject,
        ):
            with self.assertRaisesRegex(
                installer.ProductionActivationError,
                "journal_cas_failed",
            ) as raised:
                self._activate_with_fixture(labels, manifest, self._FakeLaunchctl())

        self.assertTrue(injected)
        self.assertEqual(external_bytes, destination.read_bytes())
        self.assertEqual(1, raised.exception.audit["rollback_invocation_count"])
        self.assertEqual(
            "activation_failed_rollback_incomplete",
            raised.exception.audit["status"],
        )

    def test_unexpected_final_surface_exception_rolls_back_exactly_once(self) -> None:
        labels, manifest = self._activation_fixture()
        launchctl = self._FakeLaunchctl()
        with patch.object(
            installer,
            "validate_exact_owned_launchd_surface",
            side_effect=RuntimeError("injected-final-surface-failure"),
        ):
            with self.assertRaisesRegex(
                installer.ProductionActivationError,
                "final_owned_surface_exception",
            ) as raised:
                self._activate_with_fixture(labels, manifest, launchctl)

        audit = raised.exception.audit
        self.assertEqual(1, audit["rollback_invocation_count"])
        self.assertTrue(audit["rollback_complete"], audit["rollback_failures"])
        self.assertEqual("activation_failed_rollback_complete", audit["status"])
        self.assertEqual(set(), launchctl.loaded)
        self.assertTrue(
            all(not (self.launchd / f"{label}.plist").exists() for label in labels)
        )
        self.assertEqual(
            "rollback_complete",
            json.loads(
                self.paths.plist_rollback_manifest.read_text(encoding="utf-8")
            )["status"],
        )
        persisted = json.loads(
            self.paths.activation_audit.read_text(encoding="utf-8")
        )
        self.assertEqual(audit["status"], persisted["status"])

    def test_fresh_partial_failure_removes_all_new_disk_and_loaded_jobs(self) -> None:
        labels, manifest = self._activation_fixture()
        launchctl = self._FakeLaunchctl(
            bootstrap_failures={labels[2]: "return5_before_load"}
        )
        with self.assertRaises(installer.ProductionActivationError) as raised:
            self._activate_with_fixture(labels, manifest, launchctl)

        audit = raised.exception.audit
        self.assertTrue(audit["rollback_complete"], audit["rollback_failures"])
        self.assertEqual(set(), launchctl.loaded)
        self.assertTrue(
            all(not (self.launchd / f"{label}.plist").exists() for label in labels)
        )
        self.assertEqual("rollback_complete", json.loads(
            self.paths.plist_rollback_manifest.read_text(encoding="utf-8")
        )["status"])

    def test_upgrade_failure_restores_old_loaded_and_disk_across_next_generation(self) -> None:
        name = installer.PRODUCTION_PLIST_NAMES[0]
        label = name.removesuffix(".plist")
        old_bytes = self._old_production_plist(label, "v0")
        destination = self._write_launchagent(label, old_bytes)
        labels, manifest = self._activation_fixture()
        launchctl = self._FakeLaunchctl(
            loaded={label},
            loaded_payloads={label: old_bytes},
            bootstrap_failures={labels[2]: "return5_before_load"},
        )
        with self.assertRaises(installer.ProductionActivationError) as raised:
            self._activate_with_fixture(labels, manifest, launchctl)
        self.assertTrue(raised.exception.audit["rollback_complete"])
        self.assertEqual(old_bytes, destination.read_bytes())
        self.assertEqual(old_bytes, launchctl.loaded_payloads[label])

        source = self.stable / "examples/portfolio_backtesting/launchd" / name
        next_payload = installer.plistlib.loads(source.read_bytes())
        next_payload["Version"] = "v2"
        source.write_bytes(installer.plistlib.dumps(next_payload))
        subprocess.run(
            ["git", "add", str(source.relative_to(self.stable))],
            cwd=self.stable,
            check=True,
        )
        self._commit_stable("next settled generation")
        installer.provision_stable_assets(self.paths)
        self.assertEqual(old_bytes, destination.read_bytes())
        second_labels = installer._production_labels_from_plists(self.paths)
        second_manifest = {
            "source_commit": self._head(),
            "manifest_sha256": "d" * 64,
        }
        second_launchctl = self._FakeLaunchctl(
            loaded={label},
            loaded_payloads={label: old_bytes},
            bootstrap_failures={second_labels[2]: "return5_before_load"},
        )
        with self.assertRaises(installer.ProductionActivationError):
            self._activate_with_fixture(
                second_labels, second_manifest, second_launchctl
            )
        self.assertEqual(old_bytes, destination.read_bytes())
        self.assertEqual(old_bytes, second_launchctl.loaded_payloads[label])

    def test_conflict_file_and_loaded_state_are_restored_on_failure(self) -> None:
        labels, manifest = self._activation_fixture()
        conflict = installer.CONFLICTING_JOB_LABELS[0]
        conflict_path, conflict_bytes = self._write_conflict_plist(conflict)
        launchctl = self._FakeLaunchctl(
            loaded={conflict},
            loaded_payloads={conflict: conflict_bytes},
            bootstrap_failures={labels[1]: "return5_before_load"},
        )
        with self.assertRaises(installer.ProductionActivationError) as raised:
            self._activate_with_fixture(labels, manifest, launchctl)
        self.assertTrue(raised.exception.audit["rollback_complete"])
        self.assertEqual(conflict_bytes, conflict_path.read_bytes())
        self.assertEqual({conflict}, launchctl.loaded)
        self.assertEqual(conflict_bytes, launchctl.loaded_payloads[conflict])

    def test_bootstrap_error_after_side_effect_is_cleaned(self) -> None:
        labels, manifest = self._activation_fixture()
        launchctl = self._FakeLaunchctl(
            bootstrap_failures={labels[2]: "return5_after_load"}
        )
        with self.assertRaises(installer.ProductionActivationError) as raised:
            self._activate_with_fixture(labels, manifest, launchctl)
        self.assertTrue(raised.exception.audit["rollback_complete"])
        self.assertEqual(set(), launchctl.loaded)
        self.assertTrue(
            all(not (self.launchd / f"{label}.plist").exists() for label in labels)
        )

    def test_unknown_owned_label_appearing_during_rollback_marks_incomplete(self) -> None:
        labels, manifest = self._activation_fixture()
        unknown = "local.qmt-roll.official-live.external-during-rollback"
        launchctl = self._FakeLaunchctl(
            bootstrap_failures={labels[1]: "return5_before_load"},
            inject_labels_at_domain_print={5: {unknown}},
        )

        with self.assertRaises(installer.ProductionActivationError) as raised:
            self._activate_with_fixture(labels, manifest, launchctl)

        audit = raised.exception.audit
        self.assertEqual("activation_failed_rollback_incomplete", audit["status"])
        self.assertFalse(audit["rollback_complete"])
        self.assertIn(
            f"unknown_owned_label:{unknown}",
            ",".join(audit["rollback_failures"]),
        )
        self.assertIn(unknown, launchctl.loaded)

    def test_bootout_error_after_side_effect_restores_old_job(self) -> None:
        labels, manifest = self._activation_fixture()
        conflict = installer.CONFLICTING_JOB_LABELS[0]
        conflict_path, conflict_bytes = self._write_conflict_plist(conflict)
        launchctl = self._FakeLaunchctl(
            loaded={conflict},
            loaded_payloads={conflict: conflict_bytes},
            bootout_failures={conflict: "return5_after_remove"},
            bootstrap_failures={labels[1]: "return5_before_load"},
        )
        with self.assertRaises(installer.ProductionActivationError) as raised:
            self._activate_with_fixture(labels, manifest, launchctl)
        self.assertTrue(raised.exception.audit["rollback_complete"])
        self.assertEqual({conflict}, launchctl.loaded)
        self.assertEqual(conflict_bytes, conflict_path.read_bytes())

    def test_preflight_absent_labels_loaded_late_are_ensured_absent(self) -> None:
        labels, manifest = self._activation_fixture()
        conflict = installer.CONFLICTING_JOB_LABELS[0]
        late_labels = {conflict, labels[0]}
        launchctl = self._FakeLaunchctl(
            late_load_after_preflight=late_labels,
        )

        with self.assertRaisesRegex(
            installer.ProductionActivationError,
            "owned_surface_unverified",
        ):
            self._activate_with_fixture(labels, manifest, launchctl)

        self.assertTrue(late_labels <= launchctl.late_loaded)
        self.assertFalse(
            any(
                call[1] in {"bootout", "bootstrap"}
                for call in launchctl.calls
            )
        )

    def test_post_journal_disk_drift_blocks_without_overwriting_external_bytes(self) -> None:
        label = installer.PRODUCTION_PLIST_NAMES[0].removesuffix(".plist")
        destination = self._write_launchagent(
            label,
            self._old_production_plist(label, "journaled"),
        )
        labels, manifest = self._activation_fixture()
        external_bytes = self._old_production_plist(label, "external")
        original = installer._journal_previous_installed_plists

        def journal_then_drift(*args: object, **kwargs: object):
            result = original(*args, **kwargs)
            destination.write_bytes(external_bytes)
            destination.chmod(0o600)
            return result

        launchctl = self._FakeLaunchctl()
        with patch.object(
            installer,
            "_journal_previous_installed_plists",
            side_effect=journal_then_drift,
        ):
            with self.assertRaises(
                installer.ProductionActivationError
            ) as raised:
                self._activate_with_fixture(labels, manifest, launchctl)

        audit = raised.exception.audit
        self.assertEqual(
            "activation_blocked_pre_mutation",
            audit["status"],
        )
        self.assertTrue(audit["manual_recovery_required"])
        self.assertEqual(external_bytes, destination.read_bytes())
        self.assertFalse(any(
            call[1] in {"bootout", "bootstrap"}
            for call in launchctl.calls
        ))
        self.assertEqual(
            "rollback_incomplete",
            json.loads(
                self.paths.plist_rollback_manifest.read_text(encoding="utf-8")
            )["status"],
        )

    def test_process_lock_has_one_winner_and_busy_prepare_has_no_mutation(self) -> None:
        marker = Path(self.tempdir.name) / "lock-held"
        holder_code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import install_qmt_roll_stage948_official_live_production as installer
paths = installer.ProductionInstallPaths(*map(Path, sys.argv[2:6]))
with installer._exclusive_install_lock(paths):
    Path(sys.argv[6]).write_text('held', encoding='utf-8')
    sys.stdin.read(1)
"""
        contender_code = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import install_qmt_roll_stage948_official_live_production as installer
paths = installer.ProductionInstallPaths(*map(Path, sys.argv[2:6]))
try:
    installer.provision_stable_assets(paths)
except installer.ProductionInstallError as exc:
    print(str(exc))
    raise SystemExit(7)
raise SystemExit(0)
"""
        args = [
            str(PORTFOLIO_DIR),
            str(self.main),
            str(self.stable),
            str(self.state),
            str(self.launchd),
        ]
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_code, *args, str(marker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(lambda: holder.poll() is None and holder.kill())
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists())

        contender = subprocess.run(
            [sys.executable, "-c", contender_code, *args],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(7, contender.returncode, contender.stderr)
        self.assertIn("production_install_lock_busy", contender.stdout)
        self.assertFalse(self.launchd.exists())
        self.assertEqual(0o600, self.paths.install_lock.stat().st_mode & 0o777)
        assert holder.stdin is not None
        holder.stdin.write("x")
        holder.stdin.flush()
        holder_stdout, holder_stderr = holder.communicate(timeout=10)
        self.assertEqual(0, holder.returncode, holder_stdout + holder_stderr)

    def test_activation_in_progress_crash_blocks_prepare_without_overwrite(self) -> None:
        labels, manifest = self._activation_fixture()
        old_label = labels[0]
        old_bytes = self._old_production_plist(old_label)
        destination = self._write_launchagent(old_label, old_bytes)
        staging_manifest, _ = installer._validate_prepared_staging_manifest(
            self.paths,
            prepared_source_commit=self._head(),
        )
        installer._journal_previous_installed_plists(
            self.paths,
            staging_manifest=staging_manifest,
            activation_manifest_sha256=str(manifest["manifest_sha256"]),
        )
        before_manifest = self.paths.plist_rollback_manifest.read_bytes()
        before_backup_files = {
            path.name: path.read_bytes()
            for path in (self.paths.plist_rollback_root / "plists").glob("*")
        }
        with self.assertRaisesRegex(
            installer.ProductionInstallError,
            "rollback_state_unsettled:activation_in_progress",
        ):
            installer.provision_stable_assets(self.paths)
        self.assertEqual(before_manifest, self.paths.plist_rollback_manifest.read_bytes())
        self.assertEqual(old_bytes, destination.read_bytes())
        self.assertEqual(
            before_backup_files,
            {
                path.name: path.read_bytes()
                for path in (self.paths.plist_rollback_root / "plists").glob("*")
            },
        )

    def test_disk_restore_failure_marks_rollback_incomplete_without_secondary_hash_error(self) -> None:
        name = installer.PRODUCTION_PLIST_NAMES[0]
        label = name.removesuffix(".plist")
        old_bytes = self._old_production_plist(label)
        self._write_launchagent(label, old_bytes)
        labels, manifest = self._activation_fixture()
        launchctl = self._FakeLaunchctl(
            loaded={label},
            loaded_payloads={label: old_bytes},
            bootstrap_failures={labels[2]: "return5_before_load"},
        )
        original_rename = installer._rename_noreplace

        def fail_restore(source: Path, destination: Path) -> None:
            if destination == self.launchd / name:
                raise installer.ProductionInstallError(
                    "injected_disk_restore_failure"
                )
            original_rename(source, destination)

        with (
            patch.object(
                installer,
                "_rename_noreplace",
                side_effect=fail_restore,
            ),
            self.assertRaises(installer.ProductionActivationError) as raised,
        ):
            self._activate_with_fixture(labels, manifest, launchctl)
        audit = raised.exception.audit
        self.assertEqual("activation_failed_rollback_incomplete", audit["status"])
        self.assertFalse(audit["rollback_complete"])
        self.assertTrue(
            any(
                value.startswith("rollback_restore_launchagents_disk_failed:")
                for value in audit["rollback_failures"]
            )
        )

    def test_tampered_private_backup_never_restores_or_reloads_unverified_bytes(self) -> None:
        name = installer.PRODUCTION_PLIST_NAMES[0]
        label = name.removesuffix(".plist")
        old_bytes = self._old_production_plist(label, "old")
        destination = self._write_launchagent(label, old_bytes)
        labels, manifest = self._activation_fixture()
        launchctl = self._FakeLaunchctl(
            loaded={label},
            loaded_payloads={label: old_bytes},
            bootstrap_failures={labels[1]: "return5_before_load"},
        )
        original = installer._validated_transaction_backup
        validations = 0

        def tamper_on_rollback(*args: object, **kwargs: object):
            nonlocal validations
            validations += 1
            if validations == 2:
                entry = kwargs["entry"]
                assert isinstance(entry, dict)
                backup = (
                    self.paths.plist_rollback_root
                    / str(entry["backup_relative_path"])
                )
                backup.write_bytes(b"tampered-backup")
                backup.chmod(0o600)
            return original(*args, **kwargs)

        with patch.object(
            installer,
            "_validated_transaction_backup",
            side_effect=tamper_on_rollback,
        ):
            with self.assertRaises(
                installer.ProductionActivationError
            ) as raised:
                self._activate_with_fixture(labels, manifest, launchctl)

        audit = raised.exception.audit
        self.assertEqual(
            "activation_failed_rollback_incomplete",
            audit["status"],
        )
        self.assertFalse(audit["rollback_complete"])
        self.assertTrue(
            not destination.exists()
            or destination.read_bytes() != b"tampered-backup"
        )
        self.assertNotIn(label, launchctl.loaded)

    def test_running_job_blocks_before_launchctl_or_launchagents_mutation(self) -> None:
        labels, manifest = self._activation_fixture()
        label = labels[0]
        old_bytes = self._old_production_plist(label)
        destination = self._write_launchagent(label, old_bytes)
        launchctl = self._FakeLaunchctl(loaded={label}, running={label})
        with self.assertRaisesRegex(
            installer.ProductionActivationError,
            "running_job",
        ):
            self._activate_with_fixture(labels, manifest, launchctl)
        self.assertEqual(old_bytes, destination.read_bytes())
        self.assertFalse(
            any(call[1] in {"bootout", "bootstrap"} for call in launchctl.calls)
        )

    def test_vt_setting_missing_credentials_or_wide_destination_fails_closed(self) -> None:
        candidate = Path(self.tempdir.name) / "missing-vt-setting.json"
        candidate.write_text("{}\n", encoding="utf-8")
        candidate.chmod(0o600)
        self.assertFalse(installer._vt_setting_credentials_configured(candidate))
        candidate.write_text(
            json.dumps(
                {
                    "datafeed.username": "configured",
                    "datafeed.password": "configured",
                }
            ),
            encoding="utf-8",
        )
        candidate.chmod(0o644)
        with self.assertRaisesRegex(
            installer.ProductionInstallError, "file_security_invalid"
        ):
            installer._vt_setting_credentials_configured(candidate)


if __name__ == "__main__":
    unittest.main()
