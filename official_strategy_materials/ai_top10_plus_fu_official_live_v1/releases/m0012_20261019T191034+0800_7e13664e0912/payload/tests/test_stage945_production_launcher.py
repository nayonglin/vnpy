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

    def test_lightweight_context_reexports_canonical_identity_and_splits_roots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            control = root / "control"
            signal = root / "signal"
            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(PORTFOLIO_DIR),
                    "OFFICIAL_LIVE_OUTPUT_DIR": str(control),
                    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(signal),
                }
            )
            script = """
import json
import sys

blocked_roots = (
    "pandas",
    "numpy",
    "tqsdk",
    "plotly",
    "vnpy",
    "vnpy_portfoliostrategy",
    "build_qmt_roll_stage173_forward_main_contract_data_update",
    "main_contract_mapping",
    "run_qmt_alignment_backtest",
)
before = set(sys.modules)

import qmt_roll_official_live_lightweight_context as lightweight

loaded = sorted(
    name
    for name in sys.modules
    if name not in before
    and any(name == root or name.startswith(root + ".") for root in blocked_roots)
)

import qmt_roll_official_live_config as full

print("CONTRACT=" + json.dumps({
    "loaded_after_lightweight_import": loaded,
    "version": lightweight.OFFICIAL_LIVE_VERSION,
    "alias": lightweight.OFFICIAL_LIVE_ALIAS,
    "shadow_start": lightweight.OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    "control": str(lightweight.CONTROL_OUTPUT_DIR),
    "signal": str(lightweight.SIGNAL_INPUT_DIR),
    "data": str(lightweight.DATA_ASSET_DIR),
    "lightweight_identity": [
        lightweight.OFFICIAL_LIVE_VERSION,
        lightweight.OFFICIAL_LIVE_ALIAS,
        lightweight.OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    ],
    "full_config_identity": [
        full.OFFICIAL_LIVE_VERSION,
        full.OFFICIAL_LIVE_ALIAS,
        full.OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    ],
    "lightweight_summary": str(lightweight.OFFICIAL_LIVE_SUMMARY_PATH),
    "full_config_summary": str(full.OFFICIAL_LIVE_SUMMARY_PATH),
}))
"""
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout)
        payload = json.loads(
            next(
                line
                for line in result.stdout.splitlines()
                if line.startswith("CONTRACT=")
            ).removeprefix("CONTRACT=")
        )
        self.assertEqual([], payload["loaded_after_lightweight_import"])
        self.assertEqual(
            "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
            payload["version"],
        )
        self.assertEqual("Stage847-C9-15w", payload["alias"])
        self.assertEqual("2026-07-23", payload["shadow_start"])
        self.assertEqual(control.resolve(), Path(payload["control"]).resolve())
        self.assertEqual(signal.resolve(), Path(payload["signal"]).resolve())
        self.assertEqual(
            (PORTFOLIO_DIR / "backtest_outputs").resolve(),
            Path(payload["data"]).resolve(),
        )
        self.assertEqual(
            payload["lightweight_identity"],
            payload["full_config_identity"],
        )
        self.assertEqual(
            payload["lightweight_summary"],
            payload["full_config_summary"],
        )

    def test_stage922_import_is_stdlib_lightweight_and_roots_are_split(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            control = root / "control"
            signal = root / "signal"
            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(PORTFOLIO_DIR),
                    "OFFICIAL_LIVE_OUTPUT_DIR": str(control),
                    "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(signal),
                }
            )
            script = """
import json
import sys

import run_qmt_roll_stage922_official_live_target_date_resolver as resolver

blocked_roots = (
    "pandas",
    "numpy",
    "tqsdk",
    "plotly",
    "vnpy",
    "vnpy_portfoliostrategy",
    "build_qmt_roll_stage173_forward_main_contract_data_update",
    "main_contract_mapping",
    "qmt_roll_official_live_config",
    "run_qmt_alignment_backtest",
)
loaded = sorted(
    name
    for name in sys.modules
    if any(name == root or name.startswith(root + ".") for root in blocked_roots)
)
print("CONTRACT=" + json.dumps({
    "loaded": loaded,
    "control": str(resolver.CONTROL_OUTPUT_DIR),
    "data": str(resolver.DATA_ASSET_DIR),
    "signal": str(resolver.SIGNAL_INPUT_DIR),
    "outputs": {key: str(path) for key, path in resolver._paths("fixture").items()},
}))
"""
            result = subprocess.run(
                [sys.executable, "-S", "-c", script],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout)
        payload = json.loads(
            next(
                line
                for line in result.stdout.splitlines()
                if line.startswith("CONTRACT=")
            ).removeprefix("CONTRACT=")
        )
        self.assertEqual([], payload["loaded"])
        self.assertEqual(control.resolve(), Path(payload["control"]).resolve())
        self.assertEqual(signal.resolve(), Path(payload["signal"]).resolve())
        self.assertEqual(
            (PORTFOLIO_DIR / "backtest_outputs").resolve(),
            Path(payload["data"]).resolve(),
        )
        self.assertTrue(
            all(
                Path(path).resolve().parent == control.resolve()
                for path in payload["outputs"].values()
            )
        )

    def test_stage922_fixture_semantics_cover_ready_refresh_holiday_and_cold_start(
        self,
    ) -> None:
        import run_qmt_roll_stage922_official_live_target_date_resolver as resolver

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            mapping.write_text(
                "date\n"
                "2026-03-31\n"
                "2026-04-30\n"
                "2026-05-29\n"
                "2026-06-30\n"
                "2026-07-17\n"
                "2026-07-21\n"
                "2026-07-23\n",
                encoding="utf-8",
            )
            stage173_status = root / "stage173-status.csv"
            stage173_status.write_text(
                "contract_vt_symbol,max_date\n"
                "JM609.DCE,2026-07-23\n"
                "SM609.CZCE,2026-07-23\n"
                "RB2610.SHFE,2026-07-22\n",
                encoding="utf-8",
            )
            stage173_summary = root / "stage173-summary.json"
            stage173_summary.write_text(
                json.dumps(
                    {
                        "max_saved_date": "2026-07-23",
                        "mapping_update": {"combined_max_date": "2026-07-23"},
                    }
                ),
                encoding="utf-8",
            )
            official = root / "official-summary.json"
            official.write_text(
                json.dumps(
                    {
                        "analysis_start": "2026-07-23",
                        "analysis_end": "2026-07-23",
                        "latest_available_data_date": "2026-07-23",
                    }
                ),
                encoding="utf-8",
            )

            ready = resolver.build_target_date_resolution(
                as_of=datetime.fromisoformat("2026-07-23T17:00:00"),
                data_ready_time="16:30",
                official_summary_path=official,
                stage173_summary_path=stage173_summary,
                stage173_status_path=stage173_status,
                mapping_path=mapping,
            )
            self.assertEqual("2026-07-23", ready["resolved_target_date"])
            self.assertEqual(0, ready["requires_data_update"])
            self.assertEqual(0, ready["requires_shadow_refresh"])
            self.assertEqual(
                "target_date_resolved_local_shadow_ready_fail_closed",
                ready["resolver_status"],
            )
            self.assertEqual(
                2,
                ready["stage173_target_contract_coverage"][
                    "target_date_contract_count"
                ],
            )
            self.assertEqual(
                3,
                ready["stage173_target_contract_coverage"]["contract_count"],
            )
            self.assertEqual(0, ready["order_api_called_count"])

            holiday = resolver.build_target_date_resolution(
                as_of=datetime.fromisoformat("2026-07-20T21:00:00"),
                data_ready_time="16:30",
                official_summary_path=official,
                stage173_summary_path=stage173_summary,
                stage173_status_path=stage173_status,
                mapping_path=mapping,
            )
            self.assertEqual("2026-07-17", holiday["resolved_target_date"])
            self.assertEqual(1, holiday["target_before_shadow_start"])
            self.assertEqual(
                "target_date_before_live_shadow_start_waiting_fail_closed",
                holiday["resolver_status"],
            )
            self.assertEqual(
                "main_contract_mapping_trading_calendar",
                holiday["resolver_evidence"]["trading_calendar_source"],
            )

            before_ready = resolver.build_target_date_resolution(
                as_of=datetime.fromisoformat("2026-07-23T16:00:00"),
                data_ready_time="16:30",
                official_summary_path=official,
                stage173_summary_path=stage173_summary,
                stage173_status_path=stage173_status,
                mapping_path=mapping,
            )
            self.assertEqual("2026-07-21", before_ready["resolved_target_date"])

            stage173_summary.write_text(
                json.dumps(
                    {
                        "max_saved_date": "2026-07-21",
                        "mapping_update": {"combined_max_date": "2026-07-21"},
                    }
                ),
                encoding="utf-8",
            )
            official.write_text(
                json.dumps(
                    {
                        "analysis_start": "2026-07-23",
                        "analysis_end": "2026-07-21",
                        "latest_available_data_date": "2026-07-21",
                    }
                ),
                encoding="utf-8",
            )
            stale = resolver.build_target_date_resolution(
                as_of=datetime.fromisoformat("2026-07-23T17:00:00"),
                data_ready_time="16:30",
                official_summary_path=official,
                stage173_summary_path=stage173_summary,
                stage173_status_path=stage173_status,
                mapping_path=mapping,
            )
            self.assertEqual(1, stale["requires_data_update"])
            self.assertEqual(1, stale["requires_shadow_refresh"])
            self.assertEqual(
                "target_date_resolved_requires_refresh_fail_closed",
                stale["resolver_status"],
            )

            empty_mapping = root / "empty-mapping.csv"
            empty_mapping.write_text("date\n", encoding="utf-8")
            fallback = resolver.build_target_date_resolution(
                as_of=datetime.fromisoformat("2026-07-23T17:00:00"),
                data_ready_time="16:30",
                official_summary_path=official,
                stage173_summary_path=stage173_summary,
                stage173_status_path=stage173_status,
                mapping_path=empty_mapping,
            )
            self.assertEqual(
                "weekday_fallback",
                fallback["resolver_evidence"]["trading_calendar_source"],
            )

    def test_stage922_malformed_status_schema_preserves_zero_coverage(self) -> None:
        import run_qmt_roll_stage922_official_live_target_date_resolver as resolver

        rows = [
            {"contract_vt_symbol": "JM609.DCE", "unexpected": "2026-07-23"},
            {"contract_vt_symbol": "SM609.CZCE", "unexpected": "2026-07-23"},
        ]

        self.assertEqual(
            {
                "contract_count": 0,
                "target_date_contract_count": 0,
                "coverage_ratio": 0.0,
            },
            resolver._status_contract_coverage(rows, "2026-07-23"),
        )

    def test_target_date_resolver_timeout_is_typed_fail_closed(self) -> None:
        with (
            patch.object(
                launcher.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["stage922"], 60),
            ),
            self.assertRaisesRegex(
                launcher.ProductionSessionLaunchError,
                "^production_launcher_target_date_resolver_timeout$",
            ),
        ):
            launcher._resolve_target_date({})

    def test_typed_failure_notifies_once_and_keeps_exit_two(self) -> None:
        output = io.StringIO()
        error = launcher.ProductionSessionLaunchError(
            "production_launcher_daily_data_receipt_invalid",
            boundary="daily-data-receipt",
        )
        with (
            patch.object(sys, "argv", ["stage945", "--session", "night"]),
            patch.object(launcher, "launch_session", side_effect=error),
            patch.object(
                launcher,
                "notify_official_live_failure",
                create=True,
            ) as notify,
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["night"]},
                clear=False,
            ),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            launcher.main()

        self.assertEqual(2, raised.exception.code)
        payload = json.loads(output.getvalue())
        self.assertEqual("blocked_fail_closed", payload["launcher_status"])
        self.assertEqual(0, payload["send_order_api_called_count"])
        self.assertEqual(0, payload["cancel_order_api_called_count"])
        self.assertEqual(0, payload["order_api_called_count"])
        notify.assert_called_once()
        self.assertEqual(
            "daily-data-receipt",
            notify.call_args.kwargs["boundary"],
        )

    def test_unexpected_failure_uses_stable_code_without_raw_exception(
        self,
    ) -> None:
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["stage945", "--session", "day"]),
            patch.object(
                launcher,
                "launch_session",
                side_effect=RuntimeError("CTP_PASSWORD_SENTINEL"),
            ),
            patch.object(
                launcher,
                "notify_official_live_failure",
                create=True,
            ) as notify,
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["day"]},
                clear=False,
            ),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            launcher.main()

        self.assertEqual(2, raised.exception.code)
        serialized = output.getvalue() + repr(notify.call_args)
        self.assertIn("production_launcher_unexpected_failure", serialized)
        self.assertNotIn("CTP_PASSWORD_SENTINEL", serialized)

    def test_noncanonical_owner_never_notifies(self) -> None:
        output = io.StringIO()
        error = launcher.ProductionSessionLaunchError(
            "production_launcher_daily_data_receipt_invalid",
            boundary="daily-data-receipt",
        )
        with (
            patch.object(sys, "argv", ["stage945", "--session", "day"]),
            patch.object(launcher, "launch_session", side_effect=error),
            patch.object(
                launcher,
                "notify_official_live_failure",
                create=True,
            ) as notify,
            patch.object(launcher.os, "getppid", return_value=123),
            patch.dict(os.environ, {"XPC_SERVICE_NAME": ""}, clear=False),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            launcher.main()

        self.assertEqual(2, raised.exception.code)
        notify.assert_not_called()

    def test_inactive_cold_start_and_nontrading_skips_never_notify(self) -> None:
        cases = (
            ("day", "inactive_session"),
            ("night", "cold_start"),
            ("day", "non_trading_day"),
        )
        for session, expected_skip in cases:
            with self.subTest(session=session, expected_skip=expected_skip):
                with (
                    patch.object(
                        sys,
                        "argv",
                        ["stage945", "--session", session],
                    ),
                    patch.object(launcher, "launch_session", return_value=None),
                    patch.object(
                        launcher,
                        "notify_official_live_failure",
                        create=True,
                    ) as notify,
                ):
                    launcher.main()
                notify.assert_not_called()

    def test_successful_exec_handoff_does_not_notify(self) -> None:
        def handoff(_args: argparse.Namespace) -> None:
            launcher.os.execve("/python", ["/python", "stage930"], {})

        with (
            patch.object(sys, "argv", ["stage945", "--session", "day"]),
            patch.object(launcher, "launch_session", side_effect=handoff),
            patch.object(launcher.os, "execve") as execve,
            patch.object(
                launcher,
                "notify_official_live_failure",
                create=True,
            ) as notify,
        ):
            launcher.main()

        execve.assert_called_once_with("/python", ["/python", "stage930"], {})
        notify.assert_not_called()

    def test_night_schedule_date_before_0300_uses_previous_calendar_date(
        self,
    ) -> None:
        self.assertEqual(
            "2026-07-23",
            launcher._session_notification_schedule_date(
                "night",
                datetime.fromisoformat("2026-07-24T01:00:00+08:00"),
            ),
        )
        self.assertEqual(
            "2026-07-24",
            launcher._session_notification_schedule_date(
                "night",
                datetime.fromisoformat("2026-07-24T20:55:00+08:00"),
            ),
        )
        self.assertEqual(
            "2026-07-24",
            launcher._session_notification_schedule_date(
                "day",
                datetime.fromisoformat("2026-07-24T09:00:00+08:00"),
            ),
        )

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

    def test_activation_barrier_accepts_sorted_surface_labels_without_losing_exactness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            audit, release, commit, _digest = self._write_barrier_fixture(root)
            payload = json.loads(audit.read_text(encoding="utf-8"))
            payload["launchd_surface_production_labels"] = sorted(
                launcher.PRODUCTION_ACTIVATION_LABELS
            )
            audit.write_text(json.dumps(payload), encoding="utf-8")
            audit.chmod(0o600)
            os.utime(audit, ns=(2_000_000_000, 2_000_000_000))

            with patch.object(launcher, "_git_head", return_value=commit):
                self.assertEqual(
                    (True, "activation_success_identity_verified"),
                    launcher._validate_activation_success_barrier(
                        activation_audit=audit,
                        release_manifest=release,
                    ),
                )

            payload["launchd_surface_production_labels"][-1] = payload[
                "launchd_surface_production_labels"
            ][0]
            audit.write_text(json.dumps(payload), encoding="utf-8")
            audit.chmod(0o600)
            os.utime(audit, ns=(2_000_000_000, 2_000_000_000))
            with patch.object(launcher, "_git_head", return_value=commit):
                committed, observed = launcher._validate_activation_success_barrier(
                    activation_audit=audit,
                    release_manifest=release,
                )
            self.assertFalse(committed)
            self.assertIn("activation_label_surface_mismatch", observed)

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
                self.assertIn("--production-qualification-evidence", joined)
                self.assertEqual(
                    str(launcher.PRODUCTION_QUALIFICATION_EVIDENCE),
                    command[
                        command.index("--production-qualification-evidence") + 1
                    ],
                )
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

    def test_pre_shadow_start_exits_success_before_daily_receipt_or_stage930(self) -> None:
        args = argparse.Namespace(
            session="night",
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
        resolver = {
            "resolver_status": (
                "target_date_before_live_shadow_start_waiting_fail_closed"
            ),
            "resolved_target_date": "2026-07-22",
            "official_live_shadow_analysis_start_date": "2026-07-23",
            "target_before_shadow_start": 1,
        }
        output = io.StringIO()
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": launcher.PRODUCTION_LABELS["night"]},
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
                return_value=("2026-07-22", resolver),
            ),
            patch.object(launcher, "_validate_code_qualification"),
            patch.object(launcher, "_validate_daily_data_readiness") as daily,
            patch.object(launcher, "_build_production_environment") as environment,
            patch.object(launcher.os, "execve") as execve,
            redirect_stdout(output),
        ):
            launcher.launch_session(args)

        payload = json.loads(output.getvalue())
        self.assertEqual(
            "skipped_before_live_shadow_start",
            payload["launcher_status"],
        )
        self.assertEqual("2026-07-22", payload["target_date"])
        self.assertEqual(0, payload["ctp_connection_attempted_count"])
        self.assertEqual(0, payload["order_api_called_count"])
        daily.assert_not_called()
        environment.assert_not_called()
        execve.assert_not_called()

    def test_pre_shadow_start_requires_consistent_resolver_evidence(self) -> None:
        with self.assertRaisesRegex(
            launcher.ProductionSessionLaunchError,
            "live_shadow_cold_start_evidence_invalid",
        ):
            launcher._target_is_before_live_shadow_start(
                target_date="2026-07-23",
                resolver_payload={
                    "resolver_status": (
                        "target_date_before_live_shadow_start_waiting_fail_closed"
                    ),
                    "resolved_target_date": "2026-07-23",
                    "official_live_shadow_analysis_start_date": "2026-07-23",
                    "target_before_shadow_start": 1,
                },
            )

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
            with self.assertRaisesRegex(
                launcher.ProductionSessionLaunchError,
                "free_disk_below_minimum",
            ):
                launcher._assert_minimum_free_space(
                    (path,),
                    minimum_free_bytes=sys.maxsize,
                )


if __name__ == "__main__":
    unittest.main()
