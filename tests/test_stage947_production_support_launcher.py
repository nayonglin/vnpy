from __future__ import annotations

import argparse
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

import run_qmt_roll_stage947_official_live_production_support_launcher as launcher  # noqa: E402


class Stage947ProductionSupportLauncherTest(unittest.TestCase):
    def test_all_support_jobs_are_exact_pinned_commands(self) -> None:
        expected_scripts = {
            "day-close-readonly": "run_qmt_roll_stage907_official_live_readonly_refresh_gate.py",
            "postclose-precompute": "run_qmt_roll_stage909_official_live_shadow_refresh_gate.py",
            "postclose-report": "run_qmt_roll_stage929_official_live_15w_timed_cycle.py",
            "monthly-ai-pool": "run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py",
            "health": "run_qmt_roll_stage946_official_live_production_health_check.py",
        }
        for job, spec in launcher.SUPPORT_JOB_SPECS.items():
            with self.subTest(job=job):
                command = launcher.build_support_command(spec)
                self.assertEqual(str(launcher.PYTHON_PATH), command[0])
                self.assertEqual(expected_scripts[job], Path(command[1]).name)
                self.assertEqual(list(spec.arguments), command[2:])
                self.assertNotIn("CTP_PASSWORD", " ".join(command))
                self.assertNotIn("--submit-mode", command)

    def test_support_environment_drops_secrets_and_sets_only_job_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            signal = root / "signal"
            output.mkdir()
            signal.mkdir()
            spec = launcher.SUPPORT_JOB_SPECS["postclose-precompute"]
            with (
                patch.object(launcher, "PRODUCTION_OUTPUT_ROOT", output),
                patch.object(launcher, "PRODUCTION_SIGNAL_INPUT_ROOT", signal),
            ):
                environment = launcher._build_support_environment(
                    {
                        "XPC_SERVICE_NAME": spec.label,
                        "CTP_PASSWORD": "secret",
                        "PYTHONPATH": "/tmp/injected",
                        "DYLD_FRAMEWORK_PATH": "/tmp/injected",
                    },
                    spec=spec,
                )

        self.assertEqual("1", environment["OFFICIAL_LIVE_PHASE_D_SHADOW_REFRESH_ENABLED"])
        self.assertNotIn("OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED", environment)
        for key in ("CTP_PASSWORD", "PYTHONPATH", "DYLD_FRAMEWORK_PATH"):
            self.assertNotIn(key, environment)

    def test_precompute_issues_receipt_only_after_qualified_success(self) -> None:
        spec = launcher.SUPPORT_JOB_SPECS["postclose-precompute"]
        summary = {
            "shadow_refresh_status": "shadow_refresh_completed",
            "execution_profile": "c9-15w",
            "refresh_attempted": 1,
            "target_date": "2026-07-21",
            "commands": [
                {"name": "stage173_data_update", "exit_code": 0},
                {"name": "official_live_shadow", "exit_code": 0},
            ],
        }
        result = subprocess.CompletedProcess(
            args=["precompute"],
            returncode=0,
            stdout="summary json: /private/path\n" + json.dumps(summary),
            stderr="",
        )
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        with (
            patch.object(launcher.subprocess, "run", return_value=result),
            patch.object(
                launcher,
                "_resolve_target_date",
                return_value=("2026-07-21", {}),
            ),
            patch.object(
                launcher,
                "build_and_write_production_daily_data_receipt",
            ) as issue,
        ):
            launcher._run_precompute_and_issue_daily_receipt(
                spec=spec,
                command=["python", "stage909"],
                environment={},
                manifest=manifest,
            )
        issue.assert_called_once()
        self.assertEqual(
            "2026-07-21",
            issue.call_args.kwargs["target_cutoff_date"],
        )

        summary["shadow_refresh_status"] = "shadow_refresh_command_failed"
        failed = subprocess.CompletedProcess(
            args=["precompute"],
            returncode=0,
            stdout=json.dumps(summary),
            stderr="",
        )
        with (
            patch.object(launcher.subprocess, "run", return_value=failed),
            patch.object(
                launcher,
                "build_and_write_production_daily_data_receipt",
            ) as issue_failed,
            self.assertRaisesRegex(
                launcher.ProductionSupportLaunchError,
                "precompute_not_qualified",
            ),
        ):
            launcher._run_precompute_and_issue_daily_receipt(
                spec=spec,
                command=["python", "stage909"],
                environment={},
                manifest=manifest,
            )
        issue_failed.assert_not_called()

    def test_precompute_does_not_issue_receipt_when_authoritative_target_is_stale(
        self,
    ) -> None:
        spec = launcher.SUPPORT_JOB_SPECS["postclose-precompute"]
        summary = {
            "shadow_refresh_status": "shadow_refresh_completed",
            "execution_profile": "c9-15w",
            "refresh_attempted": 1,
            "target_date": "2026-07-23",
            "commands": [
                {"name": "stage173_data_update", "exit_code": 0},
                {"name": "official_live_shadow", "exit_code": 0},
            ],
        }
        result = subprocess.CompletedProcess(
            args=["precompute"],
            returncode=0,
            stdout=json.dumps(summary),
            stderr="",
        )
        with (
            patch.object(launcher.subprocess, "run", return_value=result),
            patch.object(
                launcher,
                "_resolve_target_date",
                return_value=("2026-07-22", {}),
            ),
            patch.object(
                launcher,
                "build_and_write_production_daily_data_receipt",
            ) as issue,
            self.assertRaisesRegex(
                launcher.ProductionSupportLaunchError,
                "precompute_target_date_mismatch",
            ),
        ):
            launcher._run_precompute_and_issue_daily_receipt(
                spec=spec,
                command=["python", "stage909"],
                environment={},
                manifest={
                    "source_commit": "a" * 40,
                    "manifest_sha256": "b" * 64,
                },
            )
        issue.assert_not_called()

    def test_private_email_and_datafeed_credentials_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            email = root / "official_live_email.local.env"
            settings = root / "vt_setting.json"
            email.write_text("OFFICIAL_LIVE_EMAIL_ENABLED=1\n", encoding="utf-8")
            settings.write_text(
                json.dumps(
                    {
                        "datafeed.username": "configured",
                        "datafeed.password": "configured",
                    }
                ),
                encoding="utf-8",
            )
            email.chmod(0o600)
            settings.chmod(0o600)
            with (
                patch.object(launcher, "PRODUCTION_EMAIL_CONFIG_PATH", email),
                patch.object(launcher, "PRODUCTION_VT_SETTING_PATH", settings),
            ):
                launcher._validate_support_credentials(
                    launcher.SUPPORT_JOB_SPECS["monthly-ai-pool"]
                )
            settings.chmod(0o644)
            with (
                patch.object(launcher, "PRODUCTION_EMAIL_CONFIG_PATH", email),
                patch.object(launcher, "PRODUCTION_VT_SETTING_PATH", settings),
                self.assertRaisesRegex(
                    launcher.ProductionSupportLaunchError,
                    "vt_setting_security_invalid",
                ),
            ):
                launcher._validate_support_credentials(
                    launcher.SUPPORT_JOB_SPECS["monthly-ai-pool"]
                )

    def test_monthly_update_runs_precompute_before_issuing_new_receipt(self) -> None:
        monthly = subprocess.CompletedProcess(
            args=["stage935"],
            returncode=0,
            stdout=json.dumps(
                {"automation_status": "monthly_ai_pool_updated"}
            ),
            stderr="",
        )
        precompute = subprocess.CompletedProcess(
            args=["stage909"],
            returncode=0,
            stdout=json.dumps(
                {
                    "shadow_refresh_status": "shadow_refresh_completed",
                    "execution_profile": "c9-15w",
                    "refresh_attempted": 1,
                    "target_date": "2026-07-21",
                    "commands": [{"name": "official_live_shadow", "exit_code": 0}],
                }
            ),
            stderr="",
        )
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        with (
            patch.object(
                launcher.subprocess,
                "run",
                side_effect=[monthly, precompute],
            ) as run,
            patch.object(
                launcher,
                "_resolve_target_date",
                return_value=("2026-07-21", {}),
            ),
            patch.object(
                launcher,
                "build_and_write_production_daily_data_receipt",
            ) as issue,
        ):
            launcher._run_monthly_ai_pool_and_refresh_receipt(
                command=["python", "stage935"],
                environment={},
                manifest=manifest,
            )
        self.assertEqual(2, run.call_count)
        issue.assert_called_once()

    def test_monthly_already_current_revalidates_without_precompute(self) -> None:
        monthly = subprocess.CompletedProcess(
            args=["stage935"],
            returncode=0,
            stdout=json.dumps(
                {"automation_status": "monthly_ai_pool_already_current"}
            ),
            stderr="",
        )
        with (
            patch.object(launcher.subprocess, "run", return_value=monthly) as run,
            patch.object(
                launcher,
                "_resolve_target_date",
                return_value=("2026-07-21", {"calendar": "signed"}),
            ),
            patch.object(launcher, "_validate_daily_data_readiness") as validate,
            patch.object(
                launcher,
                "build_and_write_production_daily_data_receipt",
            ) as issue,
        ):
            launcher._run_monthly_ai_pool_and_refresh_receipt(
                command=["python", "stage935"],
                environment={},
                manifest={"source_commit": "a" * 40},
            )
        self.assertEqual(1, run.call_count)
        validate.assert_called_once()
        issue.assert_not_called()

    def test_manual_support_launch_is_blocked_before_validation(self) -> None:
        args = argparse.Namespace(job="health")
        with (
            patch.object(launcher.os, "getppid", return_value=123),
            patch.dict(os.environ, {"XPC_SERVICE_NAME": ""}, clear=False),
            patch.object(launcher, "_assert_stable_deploy_root") as stable,
            self.assertRaisesRegex(
                launcher.ProductionSupportLaunchError,
                "requires_canonical_launchd_owner",
            ),
        ):
            launcher.launch_support_job(args)
        stable.assert_not_called()


if __name__ == "__main__":
    unittest.main()
