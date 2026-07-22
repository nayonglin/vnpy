from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import run_qmt_roll_stage945_official_live_production_session_launcher as launcher  # noqa: E402


class Stage945ProductionLauncherTest(unittest.TestCase):
    def _write_barrier_fixture(
        self,
        root: Path,
        *,
        audit_status: str = "production_launchd_activated_no_ctp_connection",
        audit_commit: str | None = None,
        audit_manifest_sha256: str | None = None,
    ) -> tuple[Path, Path, str, str]:
        commit = "a" * 40
        release = {
            "source_commit": commit,
            "created_at_utc": "2026-07-21T00:00:00Z",
        }
        digest = launcher.release_manifest_digest(release)
        release["manifest_sha256"] = digest
        release_path = root / "release-manifest.json"
        release_path.write_bytes(launcher.serialize_release_manifest(release))
        release_path.chmod(0o600)
        audit_path = root / "activation.json"
        labels = list(launcher.PRODUCTION_ACTIVATION_LABELS)
        audit = {
            "status": audit_status,
            "source_commit": audit_commit or commit,
            "manifest_sha256": audit_manifest_sha256 or digest,
            "production_labels": labels,
            "launchd_surface_production_labels": labels,
            "launchd_surface_production_loaded_count": 7,
            "launchd_surface_conflict_loaded_count": 0,
            "reboot_surface_production_plist_count": 7,
            "reboot_surface_conflict_plist_count": 0,
            "ctp_connection_attempted_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
        }
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        audit_path.chmod(0o600)
        os.utime(release_path, ns=(1_000_000_000, 1_000_000_000))
        os.utime(audit_path, ns=(2_000_000_000, 2_000_000_000))
        return audit_path, release_path, commit, digest

    def test_activation_barrier_requires_exact_success_commit_manifest_and_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            audit, release, commit, _digest = self._write_barrier_fixture(root)
            with patch.object(launcher, "_git_head", return_value=commit):
                self.assertEqual(
                    (True, "activation_success_identity_verified"),
                    launcher._validate_activation_success_barrier(
                        activation_audit=audit,
                        release_manifest=release,
                    ),
                )
                committed, observed = (
                    launcher._validate_activation_success_barrier(
                        activation_audit=audit,
                        release_manifest=release,
                        expected_source_commit=commit,
                        expected_manifest_sha256="f" * 64,
                    )
                )
                self.assertFalse(committed)
                self.assertIn("activation_revalidation_mismatch", observed)

            payload = json.loads(audit.read_text(encoding="utf-8"))
            cases = (
                ("status", "activation_in_progress", "status_not_committed"),
                ("source_commit", "b" * 40, "identity_mismatch"),
                ("manifest_sha256", "c" * 64, "identity_mismatch"),
                (
                    "production_labels",
                    list(launcher.PRODUCTION_ACTIVATION_LABELS[:-1]),
                    "label_surface_mismatch",
                ),
            )
            for field_name, value, blocker in cases:
                with self.subTest(field_name=field_name):
                    changed = dict(payload)
                    changed[field_name] = value
                    audit.write_text(json.dumps(changed), encoding="utf-8")
                    audit.chmod(0o600)
                    os.utime(
                        audit,
                        ns=(2_000_000_000, 2_000_000_000),
                    )
                    with patch.object(launcher, "_git_head", return_value=commit):
                        committed, observed = (
                            launcher._validate_activation_success_barrier(
                                activation_audit=audit,
                                release_manifest=release,
                            )
                        )
                    self.assertFalse(committed)
                    self.assertIn(blocker, observed)

            audit.write_text(json.dumps(payload), encoding="utf-8")
            audit.chmod(0o600)
            os.utime(audit, ns=(500_000_000, 500_000_000))
            with patch.object(launcher, "_git_head", return_value=commit):
                committed, observed = (
                    launcher._validate_activation_success_barrier(
                        activation_audit=audit,
                        release_manifest=release,
                    )
                )
            self.assertFalse(committed)
            self.assertIn("activation_audit_stale", observed)

            os.utime(audit, ns=(2_000_000_000, 2_000_000_000))
            with patch.object(
                launcher,
                "_git_head",
                side_effect=subprocess.TimeoutExpired(["git"], 10),
            ):
                committed, observed = (
                    launcher._validate_activation_success_barrier(
                        activation_audit=audit,
                        release_manifest=release,
                    )
                )
            self.assertFalse(committed)
            self.assertIn("TimeoutExpired", observed)

    def test_missing_activation_barrier_exits_success_before_runtime_or_stage930(self) -> None:
        args = argparse.Namespace(
            session="day",
            release_manifest=str(launcher.PRODUCTION_RELEASE_MANIFEST),
            activation_receipt=str(launcher.PRODUCTION_ACTIVATION_RECEIPT),
            stage179_runtime_root=str(launcher.PRODUCTION_RUNTIME_ROOT),
            output_root=str(launcher.PRODUCTION_OUTPUT_ROOT),
            signal_input_root=str(launcher.PRODUCTION_SIGNAL_INPUT_ROOT),
        )
        output = io.StringIO()
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"]},
                clear=False,
            ),
            patch.object(launcher, "_assert_stable_deploy_root"),
            patch.object(
                launcher,
                "_validate_current_owned_launchd_surface",
                return_value=(True, "current_owned_launchd_surface_verified_exact"),
            ),
            patch.object(
                launcher,
                "_validate_activation_success_barrier",
                return_value=(False, "production_launcher_file_missing:latest.json"),
            ),
            patch.object(launcher, "_session_is_active") as session_active,
            patch.object(launcher, "_validate_release_and_receipt") as release,
            patch.object(launcher, "_resolve_target_date") as resolver,
            patch.object(launcher.os, "execve") as execve,
            redirect_stdout(output),
        ):
            result = launcher.launch_session(args)

        self.assertIsNone(result)
        payload = json.loads(output.getvalue())
        self.assertEqual(
            "skipped_activation_not_committed",
            payload["launcher_status"],
        )
        self.assertEqual(0, payload["stage930_exec_called_count"])
        self.assertEqual(0, payload["ctp_connection_attempted_count"])
        self.assertEqual(0, payload["order_api_called_count"])
        session_active.assert_not_called()
        release.assert_not_called()
        resolver.assert_not_called()
        execve.assert_not_called()

    def test_in_progress_activation_stops_before_release_identity_read(self) -> None:
        with patch.object(
            launcher,
            "_read_private_json",
            side_effect=(
                {"status": "activation_in_progress"},
                AssertionError("release identity must not be read"),
            ),
        ) as read_json:
            committed, blocker = launcher._validate_activation_success_barrier()

        self.assertFalse(committed)
        self.assertIn("activation_status_not_committed", blocker)
        self.assertEqual(1, read_json.call_count)

    def test_activation_identity_is_revalidated_after_full_release_load(self) -> None:
        args = argparse.Namespace(
            session="day",
            release_manifest=str(launcher.PRODUCTION_RELEASE_MANIFEST),
            activation_receipt=str(launcher.PRODUCTION_ACTIVATION_RECEIPT),
            stage179_runtime_root=str(launcher.PRODUCTION_RUNTIME_ROOT),
            output_root=str(launcher.PRODUCTION_OUTPUT_ROOT),
            signal_input_root=str(launcher.PRODUCTION_SIGNAL_INPUT_ROOT),
        )
        output = io.StringIO()
        manifest = {
            "source_commit": "a" * 40,
            "manifest_sha256": "b" * 64,
        }
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"]},
                clear=False,
            ),
            patch.object(launcher, "_assert_stable_deploy_root"),
            patch.object(
                launcher,
                "_validate_current_owned_launchd_surface",
                return_value=(True, "current_owned_launchd_surface_verified_exact"),
            ) as surface,
            patch.object(
                launcher,
                "_validate_activation_success_barrier",
                side_effect=(
                    (True, "activation_success_identity_verified"),
                    (False, "activation_revalidation_mismatch"),
                ),
            ) as barrier,
            patch.object(launcher, "_session_is_active", return_value=True),
            patch.object(launcher, "_assert_canonical_paths"),
            patch.object(
                launcher,
                "_validate_release_and_receipt",
                return_value=manifest,
            ),
            patch.object(launcher, "_build_production_environment") as environment,
            patch.object(launcher.os, "execve") as execve,
            redirect_stdout(output),
        ):
            launcher.launch_session(args)

        self.assertEqual(2, barrier.call_count)
        self.assertEqual(1, surface.call_count)
        self.assertEqual(
            {
                "expected_source_commit": manifest["source_commit"],
                "expected_manifest_sha256": manifest["manifest_sha256"],
            },
            barrier.call_args.kwargs,
        )
        self.assertEqual(
            "skipped_activation_not_committed",
            json.loads(output.getvalue())["launcher_status"],
        )
        environment.assert_not_called()
        execve.assert_not_called()

    def test_owned_surface_is_checked_before_activation_release_read(self) -> None:
        args = argparse.Namespace(
            session="day",
            release_manifest=str(launcher.PRODUCTION_RELEASE_MANIFEST),
            activation_receipt=str(launcher.PRODUCTION_ACTIVATION_RECEIPT),
            stage179_runtime_root=str(launcher.PRODUCTION_RUNTIME_ROOT),
            output_root=str(launcher.PRODUCTION_OUTPUT_ROOT),
            signal_input_root=str(launcher.PRODUCTION_SIGNAL_INPUT_ROOT),
        )
        output = io.StringIO()
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"]},
                clear=False,
            ),
            patch.object(launcher, "_assert_stable_deploy_root"),
            patch.object(
                launcher,
                "_validate_current_owned_launchd_surface",
                return_value=(False, "unknown_owned_label:unexpected"),
            ) as surface,
            patch.object(
                launcher,
                "_validate_activation_success_barrier",
            ) as barrier,
            patch.object(launcher, "_validate_release_and_receipt") as release,
            patch.object(launcher.os, "execve") as execve,
            redirect_stdout(output),
        ):
            launcher.launch_session(args)

        self.assertEqual(1, surface.call_count)
        barrier.assert_not_called()
        release.assert_not_called()
        execve.assert_not_called()
        self.assertEqual(
            "skipped_owned_launchd_surface_unverified",
            json.loads(output.getvalue())["launcher_status"],
        )

    def test_owned_surface_is_revalidated_immediately_before_live_environment(self) -> None:
        args = argparse.Namespace(
            session="day",
            release_manifest=str(launcher.PRODUCTION_RELEASE_MANIFEST),
            activation_receipt=str(launcher.PRODUCTION_ACTIVATION_RECEIPT),
            stage179_runtime_root=str(launcher.PRODUCTION_RUNTIME_ROOT),
            output_root=str(launcher.PRODUCTION_OUTPUT_ROOT),
            signal_input_root=str(launcher.PRODUCTION_SIGNAL_INPUT_ROOT),
        )
        manifest = {
            "source_commit": "a" * 40,
            "manifest_sha256": "b" * 64,
        }
        output = io.StringIO()
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"]},
                clear=False,
            ),
            patch.object(launcher, "_assert_stable_deploy_root"),
            patch.object(
                launcher,
                "_validate_current_owned_launchd_surface",
                side_effect=(
                    (True, "current_owned_launchd_surface_verified_exact"),
                    (False, "owned_domain_changed_d1_d2"),
                ),
            ) as surface,
            patch.object(
                launcher,
                "_validate_activation_success_barrier",
                return_value=(True, "activation_success_identity_verified"),
            ),
            patch.object(launcher, "_session_is_active", return_value=True),
            patch.object(launcher, "_assert_canonical_paths"),
            patch.object(
                launcher,
                "_validate_release_and_receipt",
                return_value=manifest,
            ),
            patch.object(launcher, "_build_preflight_environment", return_value={}),
            patch.object(
                launcher,
                "_resolve_target_date",
                return_value=("2026-07-21", {}),
            ),
            patch.object(launcher, "_validate_code_qualification"),
            patch.object(
                launcher,
                "_validate_daily_data_readiness",
                return_value={"production_calendar_status": "authorized_trading_session"},
            ),
            patch.object(launcher, "_assert_minimum_free_space"),
            patch.object(
                launcher,
                "build_stage930_command",
                return_value=[str(launcher.PYTHON_PATH), "stage930"],
            ),
            patch.object(launcher, "_build_production_environment") as environment,
            patch.object(launcher.os, "execve") as execve,
            redirect_stdout(output),
        ):
            launcher.launch_session(args)

        self.assertEqual(2, surface.call_count)
        self.assertEqual(
            "skipped_owned_launchd_surface_unverified",
            json.loads(output.getvalue())["launcher_status"],
        )
        environment.assert_not_called()
        execve.assert_not_called()

    def test_stage930_command_is_exact_c9_live_warm_persistent_profile(self) -> None:
        for session, spec in launcher.SESSION_SPECS.items():
            with self.subTest(session=session):
                command = launcher.build_stage930_command(
                    spec=spec,
                    target_date="2026-07-21",
                )
                joined = " ".join(command)
                self.assertEqual(str(launcher.PYTHON_PATH), command[0])
                self.assertEqual(str(launcher.STAGE930_SCRIPT), command[1])
                self.assertIn("--execution-profile c9-15w", joined)
                self.assertIn("--mode live-real", joined)
                self.assertIn("--submit-mode live-real", joined)
                self.assertIn("--runtime-profile production-live", joined)
                self.assertIn("--stage179-execution-mode warm", joined)
                self.assertIn("--detector-mode persistent", joined)
                self.assertIn("--target-date 2026-07-21", joined)
                self.assertIn("--release-manifest", joined)
                self.assertIn("--activation-receipt", joined)
                self.assertNotIn("--readonly-observe-reconnect-once", joined)
                self.assertIn("I_UNDERSTAND_THIS_ENABLES_FULL_AUTO_CTP_LIVE_TRADING", joined)
                self.assertIn("I_UNDERSTAND_THIS_ACTIVATES_STAGE179_WARM_CTP_EXECUTION", joined)
                self.assertNotIn("CTP_PASSWORD", joined)
                self.assertNotIn("CTP_AUTH_CODE", joined)
                self.assertEqual(
                    set(spec.required_session_names),
                    {
                        command[index + 1]
                        for index, value in enumerate(command[:-1])
                        if value == "--require-current-session-name"
                    },
                )

    def test_session_activity_handles_break_and_friday_late_night(self) -> None:
        day = launcher.SESSION_SPECS["day"]
        night = launcher.SESSION_SPECS["night"]
        cases = (
            (day, "2026-07-21T09:00:00+08:00", True),
            (day, "2026-07-21T12:00:00+08:00", False),
            (day, "2026-07-21T13:25:00+08:00", True),
            (night, "2026-07-21T20:55:00+08:00", True),
            (night, "2026-07-25T01:00:00+08:00", True),
            (night, "2026-07-26T01:00:00+08:00", False),
        )
        for spec, text, expected in cases:
            with self.subTest(session=spec.session, text=text):
                self.assertEqual(
                    expected,
                    launcher._session_is_active(
                        spec,
                        datetime.fromisoformat(text),
                    ),
                )

    def test_target_date_resolver_requires_current_authoritative_mapping(self) -> None:
        base = {
            "resolved_target_date": "2026-07-21",
            "order_api_called_count": 0,
            "resolver_evidence": {
                "trading_calendar_source": "main_contract_mapping_trading_calendar",
                "wall_clock_cutoff_date": "2026-07-21",
                "as_of": "2026-07-21 21:00:00",
                "data_ready_time": "16:30",
            },
        }

        def completed(payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["stage922"],
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

        with patch.object(launcher.subprocess, "run", return_value=completed(base)):
            target, payload = launcher._resolve_target_date({})
        self.assertEqual("2026-07-21", target)
        self.assertEqual(base, payload)

        holiday_gap = {
            **base,
            "resolved_target_date": "2026-07-17",
            "resolver_evidence": {
                **base["resolver_evidence"],
                "wall_clock_cutoff_date": "2026-07-20",
            },
        }
        with patch.object(
            launcher.subprocess,
            "run",
            return_value=completed(holiday_gap),
        ):
            target, _payload = launcher._resolve_target_date({})
        self.assertEqual("2026-07-17", target)

        fallback = {
            **base,
            "resolver_evidence": {
                **base["resolver_evidence"],
                "trading_calendar_source": "weekday_fallback",
            },
        }
        with (
            patch.object(launcher.subprocess, "run", return_value=completed(fallback)),
            self.assertRaisesRegex(
                launcher.ProductionSessionLaunchError,
                "calendar_not_authoritative",
            ),
        ):
            launcher._resolve_target_date({})

    def test_forward_calendar_allows_post_holiday_open_but_blocks_holiday(self) -> None:
        receipt = {
            "target_cutoff_date": "2026-07-17",
            "data_inventory": {
                "semantic_freshness": {
                    "next_trading_session_date": "2026-07-21",
                }
            },
        }

        def resolver(as_of: str) -> dict[str, object]:
            return {
                "resolver_evidence": {
                    "as_of": as_of,
                    "data_ready_time": "16:30",
                    "wall_clock_cutoff_date": "2026-07-20",
                }
            }

        self.assertEqual(
            "authorized_trading_session",
            launcher._validate_target_date_calendar_window(
            receipt=receipt,
            resolver_payload=resolver("2026-07-21 08:55:00"),
            now=datetime.fromisoformat("2026-07-21T08:55:00+08:00"),
            ),
        )
        self.assertEqual(
            "skipped_non_trading_day",
            launcher._validate_target_date_calendar_window(
                receipt=receipt,
                resolver_payload=resolver("2026-07-20 08:55:00"),
                now=datetime.fromisoformat("2026-07-20T08:55:00+08:00"),
            ),
        )

    def test_calendar_window_requires_same_day_after_close_receipt(self) -> None:
        receipt = {
            "target_cutoff_date": "2026-07-20",
            "data_inventory": {
                "semantic_freshness": {
                    "next_trading_session_date": "2026-07-21",
                }
            },
        }
        with self.assertRaisesRegex(
            launcher.ProductionSessionLaunchError,
            "after_close_target_date_mismatch",
        ):
            launcher._validate_target_date_calendar_window(
                receipt=receipt,
                resolver_payload={
                    "resolver_evidence": {
                        "as_of": "2026-07-21 20:55:00",
                        "data_ready_time": "16:30",
                        "wall_clock_cutoff_date": "2026-07-21",
                    }
                },
                now=datetime.fromisoformat("2026-07-21T20:55:00+08:00"),
            )

    def test_manual_or_wrong_label_launch_is_blocked_before_live_validation(self) -> None:
        args = argparse.Namespace(
            session="day",
            release_manifest=str(launcher.PRODUCTION_RELEASE_MANIFEST),
            activation_receipt=str(launcher.PRODUCTION_ACTIVATION_RECEIPT),
            stage179_runtime_root=str(launcher.PRODUCTION_RUNTIME_ROOT),
            output_root=str(launcher.PRODUCTION_OUTPUT_ROOT),
            signal_input_root=str(launcher.PRODUCTION_SIGNAL_INPUT_ROOT),
        )
        with (
            patch.object(launcher.os, "getppid", return_value=123),
            patch.dict(os.environ, {"XPC_SERVICE_NAME": ""}, clear=False),
            self.assertRaisesRegex(
                launcher.ProductionSessionLaunchError,
                "requires_canonical_launchd_owner",
            ),
        ):
            launcher.launch_session(args)

    def test_production_environment_is_allowlisted_and_drops_live_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_root = root / "output"
            signal_root = root / "signal"
            output_root.mkdir()
            signal_root.mkdir()
            environment = launcher._build_production_environment(
                {
                    "XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"],
                    "LANG": "zh_CN.UTF-8",
                    "CTP_PASSWORD": "must-not-survive",
                    "CTP_AUTH_CODE": "must-not-survive",
                    "PYTHONPATH": "/tmp/injected",
                    "DYLD_LIBRARY_PATH": "/tmp/injected-framework",
                    "UNRELATED_SECRET": "must-not-survive",
                },
                output_root=output_root,
                signal_input_root=signal_root,
            )

        self.assertEqual(
            launcher.PRODUCTION_LABELS["day"],
            environment["XPC_SERVICE_NAME"],
        )
        self.assertEqual("1", environment["OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED"])
        self.assertEqual("1", environment["OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED"])
        self.assertEqual("zh_CN.UTF-8", environment["LANG"])
        for key in (
            "CTP_PASSWORD",
            "CTP_AUTH_CODE",
            "PYTHONPATH",
            "DYLD_LIBRARY_PATH",
            "UNRELATED_SECRET",
        ):
            self.assertNotIn(key, environment)

    def test_noncanonical_deploy_root_blocks_before_release_validation(self) -> None:
        args = argparse.Namespace(
            session="day",
            release_manifest=str(launcher.PRODUCTION_RELEASE_MANIFEST),
            activation_receipt=str(launcher.PRODUCTION_ACTIVATION_RECEIPT),
            stage179_runtime_root=str(launcher.PRODUCTION_RUNTIME_ROOT),
            output_root=str(launcher.PRODUCTION_OUTPUT_ROOT),
            signal_input_root=str(launcher.PRODUCTION_SIGNAL_INPUT_ROOT),
        )
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"]},
                clear=False,
            ),
            patch.object(
                launcher,
                "PRODUCTION_DEPLOY_ROOT",
                launcher.REPO_ROOT.parent / "definitely-not-this-worktree",
            ),
            patch.object(launcher, "_validate_release_and_receipt") as validate,
            self.assertRaisesRegex(
                launcher.ProductionSessionLaunchError,
                "stable_deploy_root_missing|noncanonical_deploy_root",
            ),
        ):
            launcher.launch_session(args)
        validate.assert_not_called()

    def test_low_disk_blocks_before_exec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            usage = os.statvfs(path)
            observed_free = usage.f_bavail * usage.f_frsize
            with self.assertRaisesRegex(
                launcher.ProductionSessionLaunchError,
                "free_disk_below_minimum",
            ):
                launcher._assert_minimum_free_space(
                    (path,),
                    minimum_free_bytes=observed_free + 1,
                )


if __name__ == "__main__":
    unittest.main()
