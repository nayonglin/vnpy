from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
import run_qmt_roll_stage903_official_live_phase_d_controller as stage903
import run_qmt_roll_stage930_official_live_c9_session_daemon as stage930


class Stage372DaemonBoundaryTest(unittest.TestCase):
    def test_stage372_controller_never_runs_stage904(self) -> None:
        with patch.object(
            stage903,
            "_run_stage904",
            side_effect=AssertionError("Stage904 must stay dormant"),
        ):
            result = stage903._run_stage904_for_profile(
                STAGE372_20W_PROFILE,
                target_date="2026-07-18",
                require_broker_fill_price=False,
            )

        self.assertEqual(result["command"], [])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(
            result["summary"]["monitor_status"],
            "intraday_not_applicable_profile_disabled",
        )
        self.assertEqual(result["summary"]["order_api_called_count"], 0)

    def test_stage372_daemon_never_starts_detector(self) -> None:
        args = argparse.Namespace(
            execution_profile="stage372-20w",
            detector_mode="persistent",
            detector_max_restarts=3,
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            with patch.object(
                stage930,
                "_start_detector",
                side_effect=AssertionError("Stage941 must stay dormant"),
            ):
                supervisor = stage930._initialize_detector_supervisor(
                    args,
                    paths,
                    target_date="2026-07-18",
                )

        self.assertEqual(supervisor["enabled"], 0)
        self.assertIsNone(supervisor["process"])
        self.assertIn(
            "stage372_profile_forbids_c9_persistent_detector",
            supervisor["blockers"],
        )

    def test_stage372_fast_lane_is_profile_disabled_without_children(self) -> None:
        args = argparse.Namespace(execution_profile="stage372-20w")
        with patch.object(
            stage930,
            "_managed_tick_stream_status",
            side_effect=AssertionError("C9 fast lane must not inspect reducer feed"),
        ):
            result = stage930._run_fast_intraday_lane(
                args,
                "2026-07-18",
                {},
            )

        self.assertEqual(
            result["fast_lane_status"],
            "intraday_not_applicable_profile_disabled",
        )
        self.assertEqual(result["order_api_called_count"], 0)

    def test_stage930_passes_profile_to_stage903_command(self) -> None:
        args = argparse.Namespace(
            execution_profile="stage372-20w",
            mode="dry-run",
            shadow_refresh_mode="plan-only",
            readonly_refresh_mode="plan-only",
            readonly_wait_seconds=1,
            stage251_mode="skip",
            max_snapshot_age_seconds=300,
            tick_refresh_mode="skip",
            controller_timeout_seconds=1,
            confirm_live_real="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = {"command_log": Path(tmp) / "commands.log"}
            with patch.object(
                stage930,
                "_run_command",
                return_value={"stdout": "{}", "exit_code": 0},
            ) as run_command:
                stage930._run_stage903(args, "2026-07-18", paths)

        command = run_command.call_args.args[0]
        index = command.index("--execution-profile")
        self.assertEqual(command[index + 1], "stage372-20w")

    def test_stage903_uses_stage914_stdout_from_the_same_process(self) -> None:
        same_run_summary = {
            "execution_profile": "stage372-20w",
            "preflight_status": "production_readonly_preflight_blocked",
            "blocking_failure_count": 1,
            "run_marker": "same-process",
        }
        stale_latest_summary = {
            "execution_profile": "c9-15w-historical",
            "preflight_status": "production_readonly_preflight_passed",
            "blocking_failure_count": 0,
            "run_marker": "stale-file",
        }
        with (
            patch.object(
                stage903.subprocess,
                "run",
                return_value=SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps(same_run_summary),
                ),
            ),
            patch.object(
                stage903,
                "_read_json",
                return_value=stale_latest_summary,
            ),
        ):
            result = stage903._run_stage914(
                1,
                execution_profile=STAGE372_20W_PROFILE,
            )

        self.assertEqual(result["summary"], same_run_summary)

    def test_stage372_directory_provisioner_is_bounded_and_idempotent(self) -> None:
        script = (
            PORTFOLIO_DIR
            / "provision_qmt_roll_stage372_launchd_directories.py"
        )
        self.assertTrue(script.exists(), "Stage372 provisioner is missing")
        spec = importlib.util.spec_from_file_location(
            "stage372_directory_provisioner",
            script,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "stage179_stage372"
            plist_path = Path(tmp) / "stage372.plist"
            plist_path.write_bytes(
                plistlib.dumps(
                    {
                        "StandardOutPath": str(root / "day" / "out.log"),
                        "StandardErrorPath": str(root / "day" / "err.log"),
                        "EnvironmentVariables": {
                            "OFFICIAL_LIVE_OUTPUT_DIR": str(
                                root / "day" / "official-live"
                            ),
                            "OFFICIAL_LIVE_SIGNAL_INPUT_DIR": str(
                                root / "signal-input"
                            ),
                        },
                        "ProgramArguments": [
                            "python",
                            "daemon.py",
                            "--stage179-runtime-root",
                            str(root / "day" / "runtime"),
                        ],
                    }
                )
            )

            required = module.collect_required_directories(
                [plist_path],
                allowed_root=root,
            )
            resolved_root = root.resolve(strict=False)
            self.assertEqual(
                set(required),
                {
                    resolved_root,
                    resolved_root / "day",
                    resolved_root / "day" / "official-live",
                    resolved_root / "day" / "runtime",
                    resolved_root / "signal-input",
                },
            )
            check = module.provision_directories(required, create=False)
            self.assertEqual(check["status"], "directories_missing")
            created = module.provision_directories(required, create=True)
            self.assertEqual(created["status"], "directories_ready")
            self.assertEqual(created["launchctl_called_count"], 0)
            self.assertEqual(created["order_api_called_count"], 0)
            self.assertEqual(
                stat.S_IMODE(resolved_root.stat().st_mode),
                0o750,
            )
            repeated = module.provision_directories(required, create=True)
            self.assertEqual(repeated["created_count"], 0)
            resolved_root.chmod(0o755)
            permission_drift = module.provision_directories(
                required,
                create=False,
            )
            self.assertEqual(
                permission_drift["status"],
                "directories_permission_mismatch",
            )
            self.assertEqual(
                permission_drift["permission_mismatch_count"],
                1,
            )

            outside_plist = Path(tmp) / "outside.plist"
            outside_plist.write_bytes(
                plistlib.dumps(
                    {"StandardOutPath": str(Path(tmp) / "outside.log")}
                )
            )
            with self.assertRaisesRegex(
                ValueError,
                "stage372_launchd_directory_outside_allowed_root",
            ):
                module.collect_required_directories(
                    [outside_plist],
                    allowed_root=root,
                )


if __name__ == "__main__":
    unittest.main()
