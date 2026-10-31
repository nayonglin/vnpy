from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
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

import run_qmt_roll_stage947_official_live_production_support_launcher as launcher  # noqa: E402
import run_qmt_roll_stage945_official_live_production_session_launcher as session_launcher  # noqa: E402
import qmt_roll_official_live_postclose_pipeline as postclose_pipeline  # noqa: E402
from qmt_roll_official_ai_pool_policy import (  # noqa: E402
    OFFICIAL_AI_FIXED_PRODUCT,
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    OFFICIAL_AI_RANKED_PRODUCT_COUNT,
    OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
)


class Stage947ProductionSupportLauncherTest(unittest.TestCase):
    def _invoke_main_failure(
        self,
        *,
        job: str,
        error: BaseException,
        ppid: int = 1,
        label: str | None = None,
    ) -> tuple[object, dict[str, object], int | str | None]:
        output = io.StringIO()
        service_label = label
        if service_label is None:
            service_label = launcher.SUPPORT_JOB_SPECS[job].label
        with (
            patch.object(sys, "argv", ["stage947", "--job", job]),
            patch.object(launcher, "launch_support_job", side_effect=error),
            patch.object(
                launcher,
                "notify_official_live_failure",
                create=True,
            ) as notify,
            patch.object(launcher.os, "getppid", return_value=ppid),
            patch.dict(
                os.environ,
                {"XPC_SERVICE_NAME": service_label},
                clear=False,
            ),
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            launcher.main()
        return notify, json.loads(output.getvalue()), raised.exception.code

    def test_stage935_import_keeps_control_and_data_roots_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            control = root / "control"
            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(PORTFOLIO_DIR),
                    "OFFICIAL_LIVE_OUTPUT_DIR": str(control),
                }
            )
            script = """
import json
import sys

blocked_roots = (
    "run_qmt_alignment_backtest",
    "main_contract_mapping",
    "qmt_roll_official_live_config",
    "build_qmt_roll_stage173_forward_main_contract_data_update",
)
before = set(sys.modules)

import run_qmt_roll_stage935_official_live_monthly_ai_pool_update as stage935

loaded = sorted(
    name
    for name in sys.modules
    if name not in before
    and any(name == root or name.startswith(root + ".") for root in blocked_roots)
)
print("CONTRACT=" + json.dumps({
    "lock": str(stage935.LOCK_PATH),
    "outputs": {key: str(path) for key, path in stage935._paths("fixture").items()},
    "stage173": str(stage935.STAGE173_SUMMARY_PATH),
    "stage182_combined": str(stage935.STAGE182_COMBINED_ELIGIBILITY_PATH),
    "official_ai": str(stage935.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
    "forbidden_imports": loaded,
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
        self.assertEqual(control.resolve(), Path(payload["lock"]).resolve().parent)
        self.assertTrue(
            all(
                Path(path).resolve().parent == control.resolve()
                for path in payload["outputs"].values()
            )
        )
        self.assertEqual(
            (PORTFOLIO_DIR / "backtest_outputs").resolve(),
            Path(payload["stage173"]).resolve().parent,
        )
        self.assertNotEqual(
            payload["stage182_combined"],
            payload["official_ai"],
        )
        self.assertIn(
            "backtest_outputs",
            Path(payload["stage182_combined"]).parts,
        )
        self.assertIn(
            "official_strategy_materials",
            Path(payload["official_ai"]).parts,
        )
        self.assertEqual([], payload["forbidden_imports"])

    def test_stage935_reads_stage173_from_data_and_ai_candidates_from_control(
        self,
    ) -> None:
        import run_qmt_roll_stage935_official_live_monthly_ai_pool_update as stage935

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            control = root / "control"
            control.mkdir()
            data = root / "data"
            data.mkdir()
            mapping = data / "mapping.csv"
            mapping.write_text(
                "date\n"
                "2026-03-31\n"
                "2026-04-30\n"
                "2026-05-29\n"
                "2026-06-30\n"
                "2026-07-23\n",
                encoding="utf-8",
            )
            stage173_summary = data / "stage173-summary.json"
            stage173_summary.write_text(
                json.dumps(
                    {
                        "max_saved_date": "2026-07-23",
                        "failed_count": 0,
                        "empty_count": 0,
                        "mapping_update": {"combined_max_date": "2026-07-23"},
                    }
                ),
                encoding="utf-8",
            )
            stage182_summary = data / "stage182-summary.json"
            stage182_summary.write_text(
                json.dumps(
                    {
                        "eval_date": "2026-06-30",
                        "source_max_date": "2026-07-23",
                        "training_label_cutoff": "2026-04-30",
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            live_pool = data / "stage182-live-pool.csv"
            live_pool.write_text("product_vt_symbol\nold.SHFE\n", encoding="utf-8")
            live_eligibility = data / "stage182-live.csv"
            ranked_products = [
                "jm.DCE",
                "rb.SHFE",
                "i.DCE",
                "m.DCE",
                "ag.SHFE",
                "cu.SHFE",
                "TA.CZCE",
                "MA.CZCE",
                "au.SHFE",
                "lc.GFEX",
            ]
            self.assertEqual(OFFICIAL_AI_RANKED_PRODUCT_COUNT, len(ranked_products))
            live_rows = list(
                enumerate([*ranked_products, OFFICIAL_AI_FIXED_PRODUCT], start=1)
            )
            strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
            live_pool_text = (
                "strategy,eval_date,product_vt_symbol,"
                "predicted_product_suitability_probability,ai_rank,"
                "selection_role,source_score_type\n"
                + "".join(
                    (
                        f"{strategy},2026-06-30,{symbol},"
                        f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},{rank},"
                        f"{'fixed_fu' if symbol == OFFICIAL_AI_FIXED_PRODUCT else 'model_ranked'},"
                        "stage182_live\n"
                    )
                    for rank, symbol in live_rows
                )
            )
            live_pool.write_text(live_pool_text, encoding="utf-8")
            eligibility_header = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            )
            live_eligibility.write_text(
                eligibility_header
                + "".join(
                    (
                        f"{strategy},stage182_live,2026-06-30,{symbol},"
                        f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},{rank},"
                        f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                    )
                    for rank, symbol in live_rows
                ),
                encoding="utf-8",
            )
            report = data / "stage182-report.md"
            report.write_text("old report\n", encoding="utf-8")
            combined = data / "stage182-combined.csv"
            combined_text = eligibility_header + "".join(
                (
                    f"{strategy},stage182_live,{date},{symbol},"
                    f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},{rank},"
                    f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                )
                for date in ("2026-03-31", "2026-04-30", "2026-05-29", "2026-06-30")
                for rank, symbol in live_rows
            )
            combined.write_text(combined_text, encoding="utf-8")

            stage183_daily = control / "stage183-daily.csv"
            stage183_daily.write_text(
                "date,balance\n2026-07-23,200000\n",
                encoding="utf-8",
            )
            stage183_position = control / "stage183-position.csv"
            stage183_position.write_text(
                "date,vt_symbol,end_pos\n2026-07-23,rb2610.SHFE,0\n",
                encoding="utf-8",
            )
            stage183_candidate = control / "stage183-candidate.csv"
            stage183_candidate.write_text(
                "date,product_vt_symbol,candidate_status\n"
                "2026-07-21,rb.SHFE,rejected\n",
                encoding="utf-8",
            )
            stage183_summary = data / "stage183-summary.json"
            stage183_sources = {
                "daily": stage183_daily,
                "position_changes": stage183_position,
                "entry_candidate_snapshots": stage183_candidate,
            }
            stage183_identities = {
                name: {
                    "size": path.stat().st_size,
                    "mtime_ns": path.stat().st_mtime_ns,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for name, path in stage183_sources.items()
            }
            stage183_summary.write_text(
                json.dumps(
                    {
                        "analysis_end": "2026-07-23",
                        "source_prefix": stage935.DEFAULT_SOURCE_PREFIX,
                        "artifact_root": str(control),
                        "artifact_dates": {
                            "daily_max_date": "2026-07-23",
                            "position_changes_max_date": "2026-07-23",
                            "entry_candidate_snapshots_max_date": "2026-07-21",
                        },
                        "artifact_identities": stage183_identities,
                        "outputs": {
                            "daily": str(stage183_daily),
                            "position_changes": str(stage183_position),
                            "entry_candidate_snapshots": str(stage183_candidate),
                        },
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            candidate_live_pool = control / live_pool.name
            candidate_live_pool.write_text(live_pool_text, encoding="utf-8")
            candidate_live = control / live_eligibility.name
            candidate_live.write_text(
                eligibility_header
                + "".join(
                    (
                        f"{strategy},stage182_live,2026-06-30,{symbol},"
                        f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},{rank},"
                        f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                    )
                    for rank, symbol in live_rows
                ),
                encoding="utf-8",
            )
            candidate_combined = control / combined.name
            candidate_combined.write_text(combined_text, encoding="utf-8")
            candidate_report = control / report.name
            candidate_report.write_text("candidate report\n", encoding="utf-8")
            candidate_summary = control / stage182_summary.name
            candidate_outputs = {
                "live_pool": str(candidate_live_pool),
                "live_eligibility": str(candidate_live),
                "combined_eligibility": str(candidate_combined),
                "summary": str(candidate_summary),
                "report": str(candidate_report),
            }
            candidate_summary.write_text(
                json.dumps(
                    {
                        "eval_date": "2026-06-30",
                        "source_max_date": "2026-07-23",
                        "training_label_cutoff": "2026-04-30",
                        "source_paths": {
                            "position_changes": str(stage183_position),
                            "entry_candidate_snapshots": str(stage183_candidate),
                        },
                        "source_identities": {
                            name: stage183_identities[name]
                            for name in (
                                "position_changes",
                                "entry_candidate_snapshots",
                            )
                        },
                        "outputs": candidate_outputs,
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                as_of="2026-07-23T18:20:00",
                data_ready_time="16:30",
                mode="run",
                source_prefix=stage935.DEFAULT_SOURCE_PREFIX,
                force=True,
                skip_data_update=False,
                data_update_timeout_seconds=1,
                source_refresh_timeout_seconds=1,
                inference_timeout_seconds=1,
            )
            success = {
                "exit_code": 0,
                "elapsed_seconds": 0.0,
                "stdout_tail": "",
                "stderr_tail": "",
            }

            with (
                patch.multiple(
                    stage935,
                    CONTROL_OUTPUT_DIR=control,
                    DATA_ASSET_DIR=data,
                    ALL_FUTURES_MAPPING_PATH=mapping,
                    STAGE173_SUMMARY_PATH=stage173_summary,
                    STAGE182_SUMMARY_PATH=stage182_summary,
                    STAGE182_LIVE_POOL_PATH=live_pool,
                    STAGE182_LIVE_ELIGIBILITY_PATH=live_eligibility,
                    STAGE182_COMBINED_ELIGIBILITY_PATH=combined,
                    STAGE182_REPORT_PATH=report,
                    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH=combined,
                    STAGE183_SUMMARY_PATH=stage183_summary,
                ),
                patch.object(stage935, "_run_command", return_value=success) as run_command,
            ):
                result = stage935._run(args)
            stage173_summary_text = str(stage173_summary)
            commands = [call.args[0] for call in run_command.call_args_list]

        self.assertEqual("monthly_ai_pool_updated", result["automation_status"])
        self.assertNotIn(
            "stage173_max_saved_date_not_resolved_target_date",
            result.get("blockers", []),
        )
        self.assertEqual(
            stage173_summary_text,
            result["stage173_summary"]["path"],
        )
        self.assertEqual(
            "published",
            result["stage182_publication_receipt"]["publication_status"],
        )
        stage182_command = next(
            command for command in commands if str(stage935.STAGE182_PATH) in command
        )
        self.assertIn("--source-dir", stage182_command)
        self.assertIn("--output-dir", stage182_command)
        self.assertEqual(
            str(control),
            stage182_command[stage182_command.index("--source-dir") + 1],
        )
        self.assertEqual(
            str(control),
            stage182_command[stage182_command.index("--output-dir") + 1],
        )

    def test_receipt_or_precompute_failure_notifies_once_before_exec(self) -> None:
        cases = (
            (
                "postclose-report",
                "production_support_daily_data_receipt_invalid",
                "daily-data-receipt",
            ),
            (
                "postclose-precompute",
                "production_support_precompute_process_failed",
                "precompute",
            ),
        )
        for job, blocker, boundary in cases:
            with self.subTest(job=job):
                error = launcher.ProductionSupportLaunchError(
                    blocker,
                    boundary=boundary,
                )
                notify, payload, exit_code = self._invoke_main_failure(
                    job=job,
                    error=error,
                )

                self.assertEqual(2, exit_code)
                self.assertEqual("blocked_fail_closed", payload["launcher_status"])
                self.assertEqual(0, payload["send_order_api_called_count"])
                self.assertEqual(0, payload["cancel_order_api_called_count"])
                self.assertEqual(0, payload["order_api_called_count"])
                notify.assert_called_once()

    def test_resolver_failure_is_adapted_and_notified_without_traceback(
        self,
    ) -> None:
        with (
            patch.object(
                launcher,
                "_resolve_target_date",
                side_effect=session_launcher.ProductionSessionLaunchError(
                    "production_launcher_target_date_resolver_timeout",
                    boundary="target-date-resolver",
                ),
            ),
            self.assertRaises(launcher.ProductionSupportLaunchError) as raised,
        ):
            launcher._resolve_support_target_date({})

        error = raised.exception
        self.assertEqual(
            "production_support_target_date_resolver_failed",
            str(error),
        )
        self.assertEqual("target-date-resolver", error.boundary)
        notify, payload, exit_code = self._invoke_main_failure(
            job="postclose-report",
            error=error,
        )
        self.assertEqual(2, exit_code)
        self.assertEqual(
            "production_support_target_date_resolver_failed",
            payload["blocker"],
        )
        self.assertNotIn("Traceback", json.dumps(payload))
        notify.assert_called_once()

    def test_outer_failure_notification_uses_installed_release_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "release-manifest.json"
            manifest_path.write_text(
                json.dumps({"source_commit": "d" * 40}),
                encoding="utf-8",
            )
            with patch.object(
                launcher,
                "PRODUCTION_RELEASE_MANIFEST",
                manifest_path,
            ):
                notify, _payload, exit_code = self._invoke_main_failure(
                    job="postclose-report",
                    error=launcher.ProductionSupportLaunchError(
                        "production_support_postclose_pipeline_receipt_missing",
                        boundary="postclose-pipeline-watchdog",
                    ),
                )

        self.assertEqual(2, exit_code)
        self.assertEqual("d" * 40, notify.call_args.kwargs["release_commit"])

    def test_monthly_five_owned_email_statuses_do_not_duplicate_fallback(
        self,
    ) -> None:
        statuses = {
            "sent",
            "dry_run_written",
            "send_failed",
            "disabled",
            "blocked_missing_config",
        }
        for status in statuses:
            with self.subTest(status=status):
                result = subprocess.CompletedProcess(
                    args=["stage935"],
                    returncode=2,
                    stdout=json.dumps(
                        {
                            "automation_status": "monthly_ai_pool_update_blocked",
                            "email_result": {"email_status": status},
                        }
                    ),
                    stderr="",
                )
                with (
                    patch.object(launcher.subprocess, "run", return_value=result),
                    self.assertRaises(
                        launcher.ProductionSupportLaunchError
                    ) as raised,
                ):
                    launcher._run_monthly_ai_pool_and_refresh_receipt(
                        command=["python", "stage935"],
                        environment={},
                        manifest={"source_commit": "a" * 40},
                    )

                error = raised.exception
                self.assertTrue(error.downstream_email_attempted)
                self.assertEqual("monthly-stage935", error.boundary)
                notify, _payload, exit_code = self._invoke_main_failure(
                    job="monthly-ai-pool",
                    error=error,
                )
                self.assertEqual(2, exit_code)
                notify.assert_not_called()

    def test_monthly_skipped_or_missing_email_result_uses_fallback(self) -> None:
        outputs = (
            json.dumps(
                {
                    "automation_status": "monthly_ai_pool_update_blocked",
                    "email_result": {"email_status": "skipped_by_policy"},
                }
            ),
            json.dumps(
                {"automation_status": "monthly_ai_pool_update_blocked"}
            ),
            "not-json",
        )
        for stdout in outputs:
            with self.subTest(stdout=stdout):
                result = subprocess.CompletedProcess(
                    args=["stage935"],
                    returncode=2,
                    stdout=stdout,
                    stderr="",
                )
                with (
                    patch.object(launcher.subprocess, "run", return_value=result),
                    self.assertRaises(
                        launcher.ProductionSupportLaunchError
                    ) as raised,
                ):
                    launcher._run_monthly_ai_pool_and_refresh_receipt(
                        command=["python", "stage935"],
                        environment={},
                        manifest={"source_commit": "a" * 40},
                    )

                error = raised.exception
                self.assertFalse(error.downstream_email_attempted)
                notify, _payload, exit_code = self._invoke_main_failure(
                    job="monthly-ai-pool",
                    error=error,
                )
                self.assertEqual(2, exit_code)
                notify.assert_called_once()

    def test_monthly_updated_candidate_stops_before_receipt_refresh(
        self,
    ) -> None:
        monthly = subprocess.CompletedProcess(
            args=["stage935"],
            returncode=0,
            stdout=json.dumps(
                {
                    "automation_status": "monthly_ai_pool_updated",
                    "email_result": {"email_status": "sent"},
                }
            ),
            stderr="",
        )
        with (
            patch.object(launcher.subprocess, "run", return_value=monthly),
            patch.object(
                launcher,
                "_run_precompute_and_issue_daily_receipt",
            ) as refresh,
            self.assertRaises(launcher.ProductionSupportLaunchError) as raised,
        ):
            launcher._run_monthly_ai_pool_and_refresh_receipt(
                command=["python", "stage935"],
                environment={},
                manifest={"source_commit": "a" * 40},
            )

        error = raised.exception
        self.assertEqual("monthly-stage935", error.boundary)
        self.assertFalse(error.downstream_email_attempted)
        refresh.assert_not_called()
        notify, _payload, exit_code = self._invoke_main_failure(
            job="monthly-ai-pool",
            error=error,
        )
        self.assertEqual(2, exit_code)
        notify.assert_called_once()

    def test_health_and_noncanonical_owner_never_notify(self) -> None:
        health_error = launcher.ProductionSupportLaunchError(
            "production_support_health_failed",
            boundary="pre-exec",
        )
        health_notify, _payload, health_exit = self._invoke_main_failure(
            job="health",
            error=health_error,
        )
        self.assertEqual(2, health_exit)
        health_notify.assert_not_called()

        manual_error = launcher.ProductionSupportLaunchError(
            "production_support_daily_data_receipt_invalid",
            boundary="daily-data-receipt",
        )
        manual_notify, _payload, manual_exit = self._invoke_main_failure(
            job="postclose-report",
            error=manual_error,
            ppid=123,
            label="",
        )
        self.assertEqual(2, manual_exit)
        manual_notify.assert_not_called()

    def test_successful_report_handoff_keeps_execve_and_no_fallback(self) -> None:
        def handoff(_args: argparse.Namespace) -> None:
            launcher.os.execve("/python", ["/python", "stage929"], {"SAFE": "1"})

        with (
            patch.object(
                sys,
                "argv",
                ["stage947", "--job", "postclose-report"],
            ),
            patch.object(launcher, "launch_support_job", side_effect=handoff),
            patch.object(launcher.os, "execve") as execve,
            patch.object(
                launcher,
                "notify_official_live_failure",
                create=True,
            ) as notify,
        ):
            launcher.main()

        execve.assert_called_once_with(
            "/python",
            ["/python", "stage929"],
            {"SAFE": "1"},
        )
        notify.assert_not_called()

    def test_unexpected_support_failure_does_not_leak_secret(self) -> None:
        notify, payload, exit_code = self._invoke_main_failure(
            job="postclose-report",
            error=RuntimeError("SMTP_PASSWORD_SENTINEL"),
        )
        self.assertEqual(2, exit_code)
        serialized = json.dumps(payload) + repr(notify.call_args)
        self.assertIn("production_support_unexpected_failure", serialized)
        self.assertNotIn("SMTP_PASSWORD_SENTINEL", serialized)

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

    def test_monthly_update_without_publication_status_stays_fail_closed(self) -> None:
        monthly = subprocess.CompletedProcess(
            args=["stage935"],
            returncode=0,
            stdout=json.dumps(
                {"automation_status": "monthly_ai_pool_updated"}
            ),
            stderr="",
        )
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        with (
            patch.object(launcher.subprocess, "run", return_value=monthly) as run,
            patch.object(
                launcher,
                "_run_precompute_and_issue_daily_receipt",
            ) as refresh,
            self.assertRaisesRegex(
                launcher.ProductionSupportLaunchError,
                "production_support_monthly_ai_pool_material_publication_required",
            ),
        ):
            launcher._run_monthly_ai_pool_and_refresh_receipt(
                command=["python", "stage935"],
                environment={},
                manifest=manifest,
            )
        self.assertEqual(1, run.call_count)
        refresh.assert_not_called()

    def test_monthly_candidate_waits_for_immutable_material_publication(self) -> None:
        monthly = subprocess.CompletedProcess(
            args=["stage935"],
            returncode=0,
            stdout=json.dumps(
                {
                    "automation_status": "monthly_ai_pool_updated",
                    "material_publication_status": "publication_required",
                    "material_publication_request_path": "/private/request.json",
                }
            ),
            stderr="",
        )
        with (
            patch.object(launcher.subprocess, "run", return_value=monthly) as run,
            patch.object(
                launcher,
                "_run_precompute_and_issue_daily_receipt",
            ) as refresh,
            self.assertRaisesRegex(
                launcher.ProductionSupportLaunchError,
                "production_support_monthly_ai_pool_material_publication_required",
            ),
        ):
            launcher._run_monthly_ai_pool_and_refresh_receipt(
                command=["python", "stage935"],
                environment={},
                manifest={"source_commit": "a" * 40},
            )

        self.assertEqual(1, run.call_count)
        refresh.assert_not_called()

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

    def test_stage173_market_data_command_is_exact_and_no_submit(self) -> None:
        command = launcher._build_stage173_market_data_command("2026-08-03")

        self.assertEqual(str(launcher.PYTHON_PATH), command[0])
        self.assertEqual(
            "build_qmt_roll_stage173_forward_main_contract_data_update.py",
            Path(command[1]).name,
        )
        self.assertEqual(
            [
                "--mapping-start",
                "2026-08-01",
                "--bar-start",
                "2026-04-05",
                "--end",
                "2026-08-03",
            ],
            command[2:],
        )
        self.assertNotIn("submit", " ".join(command).lower())

    def test_market_data_refresh_can_advance_stale_target_to_schedule_cutoff(self) -> None:
        process = subprocess.CompletedProcess(
            args=["stage173"],
            returncode=0,
            stdout="{}\n",
            stderr="",
        )
        with (
            patch.object(launcher.subprocess, "run", return_value=process) as run,
            patch.object(
                launcher,
                "_resolve_support_target_date",
                return_value=("2026-08-03", {"calendar": "refreshed"}),
            ),
        ):
            result = launcher._run_market_data_worker(
                target_date="2026-08-02",
                refresh_cutoff_date="2026-08-03",
                environment={},
            )

        self.assertEqual("2026-08-03", result["target_date"])
        command = run.call_args.args[0]
        self.assertEqual("2026-04-04", command[command.index("--bar-start") + 1])
        self.assertEqual("2026-08-03", command[command.index("--end") + 1])

    def test_pipeline_monthly_email_policy_sends_update_success_only(self) -> None:
        import run_qmt_roll_stage935_official_live_monthly_ai_pool_update as stage935

        spec = launcher.SUPPORT_JOB_SPECS["monthly-ai-pool"]
        self.assertEqual(
            ("--mode", "run", "--email-policy", "updates"),
            spec.arguments,
        )
        self.assertTrue(
            stage935._should_send_email(
                {"automation_status": "monthly_ai_pool_updated"},
                "updates",
            )
        )
        for status in (
            "monthly_ai_pool_already_current",
            "monthly_ai_pool_update_blocked",
            "monthly_ai_pool_exception",
            "monthly_ai_pool_locked",
        ):
            with self.subTest(status=status):
                self.assertFalse(
                    stage935._should_send_email(
                        {"automation_status": status},
                        "updates",
                    )
                )

    def test_monthly_worker_rejects_missing_zero_api_evidence(self) -> None:
        for missing in (
            "send_order_api_called_count",
            "cancel_order_api_called_count",
            "order_api_called_count",
        ):
            payload = {
                "automation_status": "monthly_ai_pool_already_current",
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }
            payload.pop(missing)
            process = subprocess.CompletedProcess(
                args=["stage935"],
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
            with (
                self.subTest(missing=missing),
                patch.object(launcher.subprocess, "run", return_value=process),
                self.assertRaisesRegex(
                    launcher.ProductionSupportLaunchError,
                    "monthly_ai_pool_order_api_evidence_invalid",
                ),
            ):
                launcher._run_monthly_ai_pool_worker(
                    command=["python", "stage935"],
                    environment={},
                )

    def test_monthly_worker_rejects_every_updated_candidate_schema(self) -> None:
        for publication_status in (
            None,
            "publication_required",
            "future_unknown_status",
        ):
            payload = {
                "automation_status": "monthly_ai_pool_updated",
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            }
            if publication_status is not None:
                payload["material_publication_status"] = publication_status
            completed = subprocess.CompletedProcess(
                args=["stage935"],
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
            with (
                self.subTest(publication_status=publication_status),
                patch.object(launcher.subprocess, "run", return_value=completed),
                self.assertRaisesRegex(
                    launcher.ProductionSupportLaunchError,
                    "production_support_monthly_ai_pool_material_publication_required",
                ),
            ):
                launcher._run_monthly_ai_pool_worker(
                    command=["python", "stage935"],
                    environment={},
                )

    def test_postclose_report_worker_validates_real_stage929_envelope(self) -> None:
        payload = {
            "wrapper": {
                "model_tag": "stage929_official_live_15w_timed_cycle_v1",
                "target_date": "2026-08-03",
                "wrapper_exit_code": 0,
                "order_api_called_count": 0,
                "email_notification": {"email_status": "sent"},
            },
            "stage903_summary": {
                "target_date": "2026-08-03",
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
        }
        result = subprocess.CompletedProcess(
            args=["stage929"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )
        with patch.object(launcher.subprocess, "run", return_value=result):
            summary = launcher._run_postclose_report_worker(
                target_date="2026-08-03",
                command=["python", "stage929"],
                environment={},
            )

        self.assertEqual(payload["wrapper"], summary["wrapper"])
        self.assertRegex(summary["_summary_sha256"], r"^[0-9a-f]{64}$")

    def test_postclose_pipeline_orders_monthly_before_final_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "pipeline"
            state.mkdir(mode=0o700)
            calls: list[str] = []

            def market(**_kwargs):
                calls.append("market")
                return {"target_date": "2026-08-03"}

            def monthly(**_kwargs):
                calls.append("monthly")
                return {
                    "automation_status": "monthly_ai_pool_updated",
                    "resolved_target_date": "2026-08-03",
                }

            def shadow(**_kwargs):
                calls.append("shadow")
                return {"target_date": "2026-08-03"}

            def issue(**_kwargs):
                calls.append("receipt")
                return {
                    "receipt_sha256": "d" * 64,
                    "target_cutoff_date": "2026-08-03",
                }

            def report(**kwargs):
                calls.append("report")
                self.assertEqual("2026-08-03", kwargs["target_date"])
                return {"_summary_sha256": "e" * 64}

            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    state / "latest.json",
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=("2026-08-02", {"calendar": "stale"}),
                ),
                patch.object(launcher, "_run_market_data_worker", side_effect=market),
                patch.object(launcher, "_run_monthly_ai_pool_worker", side_effect=monthly),
                patch.object(
                    launcher,
                    "_run_precompute_worker",
                    side_effect=shadow,
                ),
                patch.object(launcher, "_issue_daily_data_receipt", side_effect=issue),
                patch.object(
                    launcher,
                    "_run_postclose_report_worker",
                    side_effect=report,
                ),
            ):
                result = launcher._run_postclose_pipeline(
                    environment={},
                    manifest={
                        "source_commit": "a" * 40,
                        "manifest_sha256": "b" * 64,
                    },
                )

        self.assertEqual(
            ["market", "monthly", "shadow", "receipt", "report"],
            calls,
        )
        self.assertEqual("succeeded", result["status"])
        self.assertEqual("2026-08-03", result["target_date"])
        self.assertEqual("d" * 64, result["daily_data_receipt_sha256"])
        self.assertEqual("e" * 64, result["report_summary_sha256"])
        self.assertEqual(0, result["order_api_called_count"])

    def test_postclose_pipeline_records_monthly_root_failure_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    state / "latest.json",
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=("2026-08-03", {}),
                ),
                patch.object(
                    launcher,
                    "_run_market_data_worker",
                    return_value={"target_date": "2026-08-03"},
                ),
                patch.object(
                    launcher,
                    "_run_monthly_ai_pool_worker",
                    side_effect=launcher.ProductionSupportLaunchError(
                        "production_support_monthly_ai_pool_process_failed",
                        boundary="monthly-stage935",
                    ),
                ),
                patch.object(
                    launcher,
                    "_notify_support_failure",
                    return_value={"notification_status": "sent"},
                ) as notify,
                patch.object(
                    launcher,
                    "_run_precompute_worker",
                ) as shadow,
                patch.object(launcher, "_run_postclose_report_worker") as report,
                self.assertRaisesRegex(
                    launcher.ProductionSupportLaunchError,
                    "monthly_ai_pool_process_failed",
                ) as raised,
            ):
                launcher._run_postclose_pipeline(
                    environment={},
                    manifest={
                        "source_commit": "a" * 40,
                        "manifest_sha256": "b" * 64,
                    },
                )

            payload = json.loads((state / "latest.json").read_text())

        self.assertTrue(raised.exception.downstream_email_attempted)
        self.assertEqual(1, notify.call_count)
        self.assertEqual("postclose-pipeline", notify.call_args.kwargs["job"])
        self.assertEqual("failed", payload["status"])
        self.assertEqual("refresh-monthly-ai-pool", payload["root_stage"])
        self.assertEqual(
            "production_support_monthly_ai_pool_process_failed",
            payload["root_blocker"],
        )
        self.assertTrue(
            all(
                row["status"] == "skipped_upstream_failed"
                for row in payload["stages"][4:]
            )
        )
        shadow.assert_not_called()
        report.assert_not_called()

    def test_postclose_pipeline_attributes_receipt_issue_failure_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            receipt_path = state / "latest.json"
            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    receipt_path,
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=("2026-08-03", {}),
                ),
                patch.object(
                    launcher,
                    "_run_market_data_worker",
                    return_value={"target_date": "2026-08-03"},
                ),
                patch.object(
                    launcher,
                    "_run_monthly_ai_pool_worker",
                    return_value={
                        "automation_status": "monthly_ai_pool_already_current",
                        "resolved_target_date": "2026-08-03",
                    },
                ),
                patch.object(
                    launcher,
                    "_run_precompute_worker",
                    return_value={"target_date": "2026-08-03"},
                ),
                patch.object(
                    launcher,
                    "_issue_daily_data_receipt",
                    side_effect=launcher.ProductionSupportLaunchError(
                        "production_support_daily_receipt_write_failed"
                    ),
                ),
                patch.object(
                    launcher,
                    "_notify_support_failure",
                    return_value={"notification_status": "sent"},
                ),
                self.assertRaises(launcher.ProductionSupportLaunchError),
            ):
                launcher._run_postclose_pipeline(
                    environment={},
                    manifest={
                        "source_commit": "a" * 40,
                        "manifest_sha256": "b" * 64,
                    },
                )

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("issue-daily-data-receipt", receipt["root_stage"])
        self.assertEqual("succeeded", receipt["stages"][4]["status"])
        self.assertEqual("failed", receipt["stages"][5]["status"])

    def test_postclose_pipeline_transient_receipt_write_failure_finishes_failed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            receipt_path = state / "latest.json"
            real_write = postclose_pipeline.write_postclose_pipeline_receipt
            attempts = 0

            def fail_second_write(path: Path, payload: dict[str, object]) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 2:
                    raise OSError("transient receipt write failure")
                real_write(path, payload)

            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    receipt_path,
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=("2026-08-03", {}),
                ),
                patch.object(
                    launcher,
                    "write_postclose_pipeline_receipt",
                    side_effect=fail_second_write,
                ),
                patch.object(
                    launcher,
                    "_notify_support_failure",
                    return_value={"notification_status": "sent"},
                ) as notify,
                self.assertRaises(launcher.ProductionSupportLaunchError),
            ):
                launcher._run_postclose_pipeline(
                    environment={},
                    manifest={
                        "source_commit": "a" * 40,
                        "manifest_sha256": "b" * 64,
                    },
                )

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("failed", receipt["status"])
        self.assertEqual("resolve-target", receipt["root_stage"])
        self.assertEqual("failed", receipt["stages"][0]["status"])
        self.assertEqual(1, notify.call_count)

    def test_postclose_pipeline_transient_final_write_failure_finishes_failed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            receipt_path = state / "latest.json"
            real_write = postclose_pipeline.write_postclose_pipeline_receipt

            def fail_success_receipt(
                path: Path,
                payload: dict[str, object],
            ) -> None:
                if payload.get("status") == "succeeded":
                    raise OSError("transient final receipt write failure")
                real_write(path, payload)

            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    receipt_path,
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=("2026-08-03", {}),
                ),
                patch.object(
                    launcher,
                    "_run_market_data_worker",
                    return_value={"target_date": "2026-08-03"},
                ),
                patch.object(
                    launcher,
                    "_run_monthly_ai_pool_worker",
                    return_value={
                        "automation_status": "monthly_ai_pool_already_current",
                        "resolved_target_date": "2026-08-03",
                    },
                ),
                patch.object(
                    launcher,
                    "_run_precompute_worker",
                    return_value={"target_date": "2026-08-03"},
                ),
                patch.object(
                    launcher,
                    "_issue_daily_data_receipt",
                    return_value={
                        "receipt_sha256": "d" * 64,
                        "target_cutoff_date": "2026-08-03",
                    },
                ),
                patch.object(
                    launcher,
                    "_run_postclose_report_worker",
                    return_value={"_summary_sha256": "e" * 64},
                ),
                patch.object(
                    launcher,
                    "write_postclose_pipeline_receipt",
                    side_effect=fail_success_receipt,
                ),
                patch.object(
                    launcher,
                    "_notify_support_failure",
                    return_value={"notification_status": "sent"},
                ) as notify,
                self.assertRaises(launcher.ProductionSupportLaunchError),
            ):
                launcher._run_postclose_pipeline(
                    environment={},
                    manifest={
                        "source_commit": "a" * 40,
                        "manifest_sha256": "b" * 64,
                    },
                )

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("failed", receipt["status"])
        self.assertEqual("generate-postclose-report", receipt["root_stage"])
        self.assertEqual("failed", receipt["stages"][-1]["status"])
        self.assertEqual(1, notify.call_count)

    def test_postclose_pipeline_transient_failed_terminal_write_recovers_failure(
        self,
    ) -> None:
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        schedule_date = launcher.datetime.now().astimezone().date().isoformat()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            receipt_path = state / "latest.json"
            real_write = postclose_pipeline.write_postclose_pipeline_receipt
            failed_terminal_attempts = 0

            def fail_first_failed_terminal_write(
                path: Path,
                payload: dict[str, object],
            ) -> None:
                nonlocal failed_terminal_attempts
                if payload.get("status") == "failed":
                    failed_terminal_attempts += 1
                    if failed_terminal_attempts == 1:
                        raise OSError("transient failed terminal write failure")
                real_write(path, payload)

            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    receipt_path,
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=("2026-08-03", {}),
                ),
                patch.object(
                    launcher,
                    "_run_market_data_worker",
                    return_value={"target_date": "2026-08-03"},
                ),
                patch.object(
                    launcher,
                    "_run_monthly_ai_pool_worker",
                    side_effect=launcher.ProductionSupportLaunchError(
                        "production_support_monthly_ai_pool_process_failed",
                        boundary="monthly-stage935",
                    ),
                ),
                patch.object(
                    launcher,
                    "write_postclose_pipeline_receipt",
                    side_effect=fail_first_failed_terminal_write,
                ),
                patch.object(
                    launcher,
                    "_notify_support_failure",
                    return_value={"notification_status": "sent"},
                ) as notify,
            ):
                with self.assertRaises(launcher.ProductionSupportLaunchError):
                    launcher._run_postclose_pipeline(
                        environment={},
                        manifest=manifest,
                    )

                watchdog = launcher._inspect_postclose_pipeline_watchdog(
                    manifest=manifest,
                    schedule_date=schedule_date,
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(2, failed_terminal_attempts)
        self.assertEqual("failed", receipt["status"])
        self.assertEqual("refresh-monthly-ai-pool", receipt["root_stage"])
        self.assertEqual("failed", receipt["stages"][3]["status"])
        self.assertEqual("root_failure_already_recorded", watchdog["watchdog_status"])
        self.assertEqual(1, notify.call_count)

    def test_pre_receipt_resolver_failure_has_one_canonical_root_notification(
        self,
    ) -> None:
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        schedule_date = launcher.datetime.now().astimezone().date().isoformat()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            receipt_path = state / "latest.json"
            with (
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT",
                    receipt_path,
                ),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    side_effect=launcher.ProductionSupportLaunchError(
                        "production_support_target_date_resolver_failed",
                        boundary="target-date-resolver",
                    ),
                ),
                patch.object(
                    launcher,
                    "_notify_support_failure",
                    return_value={"notification_status": "sent"},
                ) as notify,
            ):
                with self.assertRaises(launcher.ProductionSupportLaunchError):
                    launcher._run_postclose_pipeline(
                        environment={},
                        manifest=manifest,
                    )

                watchdog = launcher._inspect_postclose_pipeline_watchdog(
                    manifest=manifest,
                    schedule_date=schedule_date,
                )
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("failed", receipt["status"])
        self.assertEqual("resolve-target", receipt["root_stage"])
        self.assertEqual("root_failure_already_recorded", watchdog["watchdog_status"])
        self.assertEqual(1, notify.call_count)

    def test_postclose_watchdog_never_spawns_workers_for_terminal_states(self) -> None:
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        for status, expected in (
            ("running", "deferred_pipeline_running"),
            ("succeeded", "already_satisfied"),
            ("failed", "root_failure_already_recorded"),
        ):
            with self.subTest(status=status):
                with (
                    patch.object(
                        launcher,
                        "load_and_validate_postclose_pipeline_receipt",
                        return_value={
                            "status": status,
                            "pipeline_run_id": "c" * 32,
                            "root_stage": (
                                "refresh-monthly-ai-pool"
                                if status == "failed"
                                else ""
                            ),
                            "root_blocker": "root" if status == "failed" else "",
                            "email_disposition": (
                                {"notification_status": "sent"}
                                if status == "failed"
                                else {}
                            ),
                            "order_api_called_count": 0,
                        },
                    ),
                    patch.object(launcher.subprocess, "run") as run,
                ):
                    result = launcher._inspect_postclose_pipeline_watchdog(
                        manifest=manifest,
                        schedule_date="2026-08-03",
                    )
                self.assertEqual(expected, result["watchdog_status"])
                self.assertEqual(0, result["order_api_called_count"])
                run.assert_not_called()

    def test_postclose_watchdog_supplements_incomplete_root_email_delivery(self) -> None:
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        receipt = {
            "status": "failed",
            "pipeline_run_id": "c" * 32,
            "root_stage": "refresh-shadow",
            "root_blocker": "production_support_precompute_process_failed",
            "email_disposition": {"notification_status": "send_failed"},
            "order_api_called_count": 0,
        }
        with (
            patch.object(
                launcher,
                "load_and_validate_postclose_pipeline_receipt",
                return_value=receipt,
            ),
            patch.object(
                launcher,
                "_notify_support_failure",
                return_value={"notification_status": "suppressed_cooldown"},
            ) as notify,
        ):
            result = launcher._inspect_postclose_pipeline_watchdog(
                manifest=manifest,
                schedule_date="2026-08-03",
            )

        self.assertEqual(
            "suppressed_cooldown",
            result["email_disposition"]["notification_status"],
        )
        self.assertEqual("a" * 40, notify.call_args.kwargs["release_commit"])

    def test_monthly_retry_runs_only_for_first_ai_pool_root_failure(self) -> None:
        payload = postclose_pipeline.new_postclose_pipeline_receipt(
            pipeline_run_id="a" * 32,
            schedule_date="2026-08-03",
            target_date="2026-08-03",
            source_commit="b" * 40,
            manifest_sha256="c" * 64,
            generated_at_utc="2026-08-03T08:35:00Z",
        )
        for stage, status in (
            ("resolve-target", "succeeded"),
            ("refresh-market-data", "succeeded"),
            ("check-monthly-ai-pool", "succeeded"),
            ("refresh-monthly-ai-pool", "failed"),
        ):
            payload = postclose_pipeline.record_postclose_pipeline_stage(
                payload,
                stage=stage,
                status=status,
                started_at_utc="2026-08-03T08:35:00Z",
                finished_at_utc="2026-08-03T08:35:01Z",
                blocker=(
                    "production_support_monthly_ai_pool_process_failed"
                    if status == "failed"
                    else ""
                ),
            )
        payload = postclose_pipeline.finish_postclose_pipeline_receipt(
            payload,
            status="failed",
            root_blocker="production_support_monthly_ai_pool_process_failed",
            email_disposition={"notification_status": "sent"},
            finished_at_utc="2026-08-03T08:35:02Z",
        )
        with (
            patch.object(
                launcher,
                "load_and_validate_postclose_pipeline_receipt",
                return_value=payload,
            ),
            patch.object(
                launcher,
                "_run_postclose_pipeline",
                return_value={"status": "succeeded", "order_api_called_count": 0},
            ) as run,
            patch.object(launcher, "_validate_support_credentials") as credentials,
        ):
            result = launcher._run_postclose_pipeline_retry(
                environment={},
                manifest={
                    "source_commit": "b" * 40,
                    "manifest_sha256": "c" * 64,
                },
                schedule_date="2026-08-03",
            )

        self.assertEqual("succeeded", result["status"])
        credentials.assert_called_once_with(
            launcher.SUPPORT_JOB_SPECS["monthly-ai-pool"]
        )
        run.assert_called_once_with(
            environment={},
            manifest={"source_commit": "b" * 40, "manifest_sha256": "c" * 64},
            retry_of="a" * 32,
        )

    def test_retry_archives_original_receipt_and_binds_retry_identity(self) -> None:
        manifest = {"source_commit": "b" * 40, "manifest_sha256": "c" * 64}
        schedule_date = launcher.datetime.now().astimezone().date().isoformat()
        original = postclose_pipeline.new_postclose_pipeline_receipt(
            pipeline_run_id="a" * 32,
            schedule_date=schedule_date,
            target_date=schedule_date,
            source_commit=manifest["source_commit"],
            manifest_sha256=manifest["manifest_sha256"],
            generated_at_utc="2026-08-03T08:35:00Z",
        )
        for stage, status in (
            ("resolve-target", "succeeded"),
            ("refresh-market-data", "succeeded"),
            ("check-monthly-ai-pool", "succeeded"),
            ("refresh-monthly-ai-pool", "failed"),
        ):
            original = postclose_pipeline.record_postclose_pipeline_stage(
                original,
                stage=stage,
                status=status,
                blocker=(
                    "production_support_monthly_ai_pool_process_failed"
                    if status == "failed"
                    else ""
                ),
                started_at_utc="2026-08-03T08:35:00Z",
                finished_at_utc="2026-08-03T08:35:01Z",
            )
        original = postclose_pipeline.finish_postclose_pipeline_receipt(
            original,
            status="failed",
            root_blocker="production_support_monthly_ai_pool_process_failed",
            email_disposition={"notification_status": "sent"},
            finished_at_utc="2026-08-03T08:35:02Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "pipeline"
            state.mkdir(mode=0o700)
            latest = state / "latest.json"
            postclose_pipeline.write_postclose_pipeline_receipt(latest, original)
            with (
                patch.object(launcher, "PRODUCTION_POSTCLOSE_PIPELINE_RECEIPT", latest),
                patch.object(
                    launcher,
                    "PRODUCTION_POSTCLOSE_PIPELINE_LOCK",
                    state / "pipeline.lock",
                ),
                patch.object(
                    launcher,
                    "_resolve_support_target_date",
                    return_value=(schedule_date, {}),
                ),
                patch.object(
                    launcher,
                    "_run_market_data_worker",
                    return_value={"target_date": schedule_date},
                ),
                patch.object(
                    launcher,
                    "_run_monthly_ai_pool_worker",
                    return_value={
                        "automation_status": "monthly_ai_pool_updated",
                        "resolved_target_date": schedule_date,
                    },
                ),
                patch.object(
                    launcher,
                    "_run_precompute_worker",
                    return_value={"target_date": schedule_date},
                ),
                patch.object(
                    launcher,
                    "_issue_daily_data_receipt",
                    return_value={
                        "receipt_sha256": "d" * 64,
                        "target_cutoff_date": schedule_date,
                    },
                ),
                patch.object(
                    launcher,
                    "_run_postclose_report_worker",
                    return_value={"_summary_sha256": "e" * 64},
                ),
            ):
                retried = launcher._run_postclose_pipeline(
                    environment={},
                    manifest=manifest,
                    retry_of="a" * 32,
                )

            archived = json.loads(
                (state / f"{'a' * 32}.json").read_text(encoding="utf-8")
            )

        self.assertEqual("a" * 32, archived["pipeline_run_id"])
        self.assertEqual("failed", archived["status"])
        self.assertEqual("a" * 32, retried["retry_of"])
        self.assertEqual("succeeded", retried["status"])

    def test_launchd_postclose_precompute_routes_to_pipeline(self) -> None:
        args = argparse.Namespace(job="postclose-precompute")
        spec = launcher.SUPPORT_JOB_SPECS[args.job]
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(os.environ, {"XPC_SERVICE_NAME": spec.label}, clear=False),
            patch.object(launcher, "_assert_stable_deploy_root"),
            patch.object(launcher, "_assert_canonical_paths"),
            patch.object(
                launcher,
                "_validate_release_and_receipt",
                return_value={
                    "source_commit": "a" * 40,
                    "manifest_sha256": "b" * 64,
                },
            ),
            patch.object(launcher, "_validate_code_qualification"),
            patch.object(launcher, "_build_support_environment", return_value={}),
            patch.object(launcher, "_validate_support_credentials"),
            patch.object(launcher, "_run_postclose_pipeline") as pipeline_run,
            patch.object(
                launcher,
                "_run_precompute_and_issue_daily_receipt",
            ) as legacy,
        ):
            launcher.launch_support_job(args)

        pipeline_run.assert_called_once()
        legacy.assert_not_called()

    def test_watchdog_and_noop_retry_do_not_require_worker_credentials(self) -> None:
        args = argparse.Namespace(job="postclose-report")
        spec = launcher.SUPPORT_JOB_SPECS[args.job]
        manifest = {"source_commit": "a" * 40, "manifest_sha256": "b" * 64}
        with (
            patch.object(launcher.os, "getppid", return_value=1),
            patch.dict(os.environ, {"XPC_SERVICE_NAME": spec.label}, clear=False),
            patch.object(launcher, "_assert_stable_deploy_root"),
            patch.object(launcher, "_assert_canonical_paths"),
            patch.object(
                launcher,
                "_validate_release_and_receipt",
                return_value=manifest,
            ),
            patch.object(launcher, "_validate_code_qualification"),
            patch.object(launcher, "_build_support_environment", return_value={}),
            patch.object(launcher, "_validate_support_credentials") as credentials,
            patch.object(
                launcher,
                "_inspect_postclose_pipeline_watchdog",
                return_value={"watchdog_status": "already_satisfied"},
            ),
        ):
            launcher.launch_support_job(args)
        credentials.assert_not_called()

        with (
            patch.object(
                launcher,
                "load_and_validate_postclose_pipeline_receipt",
                return_value={"status": "succeeded"},
            ),
            patch.object(launcher, "_validate_support_credentials") as credentials,
        ):
            result = launcher._run_postclose_pipeline_retry(
                environment={},
                manifest=manifest,
                schedule_date="2026-08-03",
            )
        self.assertEqual("already_satisfied", result["retry_status"])
        credentials.assert_not_called()

    def test_support_failure_returns_pipeline_notification_disposition(self) -> None:
        with patch.object(
            launcher,
            "notify_official_live_failure",
            return_value={"notification_status": "sent", "fingerprint": "f" * 64},
        ) as notify:
            result = launcher._notify_support_failure(
                job="postclose-pipeline",
                boundary="postclose-pipeline:refresh-monthly-ai-pool",
                blocker="production_support_monthly_ai_pool_process_failed",
                pipeline_run_id="a" * 32,
                root_stage="refresh-monthly-ai-pool",
                release_commit="b" * 40,
            )

        self.assertEqual("sent", result["notification_status"])
        self.assertEqual("a" * 32, notify.call_args.kwargs["pipeline_run_id"])
        self.assertEqual(
            "refresh-monthly-ai-pool",
            notify.call_args.kwargs["root_stage"],
        )
        self.assertEqual("b" * 40, notify.call_args.kwargs["release_commit"])

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
