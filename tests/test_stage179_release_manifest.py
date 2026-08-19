from __future__ import annotations

import copy
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


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_stage179_release_manifest as builder
import build_qmt_roll_stage179_production_qualification_bundle as bundle_builder
import build_qmt_roll_stage179_rollback_guard as rollback_guard
from build_qmt_roll_stage179_release_manifest import build_release_manifest_file
from qmt_roll_official_execution_profile import (
    C9_15W_PROFILE,
    STAGE372_20W_PROFILE,
)
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
        (self.repo / ".gitignore").write_text(
            ".py311\n*.local.env\n.pytest_cache/\n__pycache__/\n*.pyc\n",
            encoding="utf-8",
        )
        for suite_id in builder.PRODUCTION_REQUIRED_TEST_SUITES:
            test_path = self.repo / suite_id
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(
                f"# committed production evidence fixture for {suite_id}\n",
                encoding="utf-8",
            )
        self._git("add", ".gitignore", "a.py", "b.json", "tests")
        self._git("commit", "-m", "base")
        self.commit = self._git("rev-parse", "HEAD").stdout.strip()
        (self.repo / ".py311").symlink_to(Path(sys.executable).resolve().parents[1])
        env_file = (
            self.repo
            / "examples/portfolio_backtesting/ctp_live.local.env"
        )
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text(
            "export CTP_BROKERID=test-broker\n"
            "export CTP_USERID=test-account\n",
            encoding="utf-8",
        )
        env_file.chmod(0o600)
        self.manifest_path = Path(self.tempdir.name) / "release.json"

    def _private_json(
        self,
        bundle: Path,
        name: str,
        payload: dict[str, object],
    ) -> dict[str, str]:
        path = bundle / name
        encoded = builder.serialize_production_qualification_evidence(payload)
        path.write_bytes(encoded)
        path.chmod(0o600)
        return {
            "artifact_path": name,
            "artifact_sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def _private_bytes(
        self,
        bundle: Path,
        name: str,
        raw: bytes,
    ) -> dict[str, str]:
        path = bundle / name
        path.write_bytes(raw)
        path.chmod(0o600)
        return {
            "artifact_path": name,
            "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        }

    def _production_evidence(
        self,
        *,
        critical_files: tuple[str, ...],
        capture_account_fingerprints: tuple[str, str] | None = None,
    ) -> tuple[Path, dict[str, object]]:
        bundle = Path(
            tempfile.mkdtemp(
                prefix="qualification-bundle-",
                dir=self.tempdir.name,
            )
        )
        bundle.chmod(0o700)
        rows = builder.release_critical_file_rows(
            repo_root=self.repo,
            critical_files=critical_files,
        )
        tree = builder.release_tree_fingerprint(rows)
        runtime_identity = builder._production_runtime_identity(self.repo)
        runner_environment_receipts: dict[str, dict[str, object]] = {}
        for environment_kind, readonly in (
            ("pytest", False),
            ("readonly", True),
        ):
            home = bundle / f"fixture-{environment_kind}-home"
            temp_dir = bundle / f"fixture-{environment_kind}-tmp"
            home.mkdir(mode=0o700)
            temp_dir.mkdir(mode=0o700)
            environment = builder.build_trusted_runner_environment(
                home=home,
                temp_dir=temp_dir,
                readonly=readonly,
            )
            runner_environment_receipts[environment_kind] = (
                builder.trusted_runner_environment_receipt(
                    environment,
                    readonly=readonly,
                )
            )
        reviewed_at = "2026-07-21T05:55:00Z"
        review_report_pointer = self._private_json(
            bundle,
            "raw-independent-review-report.json",
            {
                "schema_version": 1,
                "artifact_kind": "independent_production_review_report",
                "review_id": "review-run-179",
                "reviewer_identity": "codex-agent-independent-42",
                "reviewed_at_utc": reviewed_at,
                "source_commit": self.commit,
                "tree_fingerprint": tree,
                "findings": [
                    {
                        "finding_id": "P2-1",
                        "severity": "P2",
                        "status": "open",
                    },
                    {
                        "finding_id": "P2-2",
                        "severity": "P2",
                        "status": "open",
                    },
                ],
            },
        )
        review_pointer = self._private_json(
            bundle,
            "independent-review.json",
            {
                "schema_version": 1,
                "artifact_kind": "independent_production_review",
                "review_kind": "independent",
                "review_id": "review-run-179",
                "reviewer_identity": "codex-agent-independent-42",
                "reviewed_at_utc": reviewed_at,
                "source_commit": self.commit,
                "tree_fingerprint": tree,
                "p0_count": 0,
                "p1_count": 0,
                "p2_count": 2,
                "report_artifact_path": review_report_pointer["artifact_path"],
                "report_artifact_sha256": review_report_pointer[
                    "artifact_sha256"
                ],
            },
        )
        critical_hashes = {
            str(row["path"]): str(row["sha256"]) for row in rows
        }
        test_pointers: list[dict[str, str]] = []
        test_digests: dict[str, str] = {}
        pytest_invocations: list[dict[str, object]] = []
        for index, suite_id in enumerate(builder.PRODUCTION_REQUIRED_TEST_SUITES):
            junit_pointer = self._private_bytes(
                bundle,
                f"raw-pytest-{index:02d}.xml",
                (
                    f'<testsuites><testsuite name="{suite_id}">'
                    '<testcase classname="production" name="passes" />'
                    "</testsuite></testsuites>\n"
                ).encode("utf-8"),
            )
            exit_pointer = self._private_bytes(
                bundle,
                f"raw-pytest-{index:02d}.exit-status",
                b"0\n",
            )
            output_pointer = self._private_bytes(
                bundle,
                f"raw-pytest-{index:02d}.output",
                b"synthetic trusted-runner fixture output\n",
            )
            pointer = self._private_json(
                bundle,
                f"pytest-{index:02d}.json",
                {
                    "schema_version": 1,
                    "artifact_kind": "pytest_suite_result",
                    "suite_id": suite_id,
                    "status": "passed",
                    "passed_count": 1,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "source_commit": self.commit,
                    "tree_fingerprint": tree,
                    "test_file_sha256": critical_hashes[suite_id],
                    "generated_at_utc": "2026-07-21T05:56:00Z",
                    "pytest_exit_code": 0,
                    "exit_status_artifact_path": exit_pointer["artifact_path"],
                    "exit_status_artifact_sha256": exit_pointer[
                        "artifact_sha256"
                    ],
                    "junit_artifact_path": junit_pointer["artifact_path"],
                    "junit_artifact_sha256": junit_pointer["artifact_sha256"],
                },
            )
            pointer["suite_id"] = suite_id
            test_pointers.append(pointer)
            test_digests[suite_id] = pointer["artifact_sha256"]
            pytest_argv = [
                runtime_identity["python_realpath"],
                "-m",
                "pytest",
                "-q",
                suite_id,
                f"--junitxml={bundle / junit_pointer['artifact_path']}",
                "-o",
                f"junit_suite_name={suite_id}",
                "-p",
                "no:cacheprovider",
            ]
            scheduler_policy = builder.PRODUCTION_DIRECT_SCHEDULER_POLICY
            if suite_id == builder.PRODUCTION_PERFORMANCE_TEST_SUITE:
                pytest_argv = [
                    builder.PRODUCTION_PERFORMANCE_TASKPOLICY_PATH,
                    "-a",
                    *pytest_argv,
                ]
                scheduler_policy = (
                    builder.PRODUCTION_PERFORMANCE_SCHEDULER_POLICY
                )
            pytest_invocations.append(
                {
                    "suite_id": suite_id,
                    "invocation_nonce": f"{index + 1:032x}",
                    "argv": pytest_argv,
                    "python_realpath": runtime_identity["python_realpath"],
                    "python_sha256": runtime_identity["python_sha256"],
                    "vnpy_ctp_extension_sha256s": runtime_identity[
                        "vnpy_ctp_extension_sha256s"
                    ],
                    "formal_framework_executable_sha256s": runtime_identity[
                        "formal_framework_executable_sha256s"
                    ],
                    "cwd_realpath": runtime_identity["cwd_realpath"],
                    "started_at_utc": "2026-07-21T05:55:30Z",
                    "finished_at_utc": "2026-07-21T05:55:40Z",
                    "returncode": 0,
                    "test_file_sha256": critical_hashes[suite_id],
                    "junit_artifact_sha256": junit_pointer["artifact_sha256"],
                    "exit_status_artifact_sha256": exit_pointer[
                        "artifact_sha256"
                    ],
                    "output_artifact_path": output_pointer["artifact_path"],
                    "output_artifact_sha256": output_pointer["artifact_sha256"],
                    "environment_sha256": runner_environment_receipts[
                        "pytest"
                    ]["environment_sha256"],
                    "scheduler_policy": scheduler_policy,
                }
            )
        aggregate_pointer = self._private_json(
            bundle,
            "selected-suite-aggregate.json",
            {
                "schema_version": 1,
                "artifact_kind": "pytest_selected_suite_aggregate",
                "status": "passed",
                "source_commit": self.commit,
                "tree_fingerprint": tree,
                "generated_at_utc": "2026-07-21T05:57:00Z",
                "suite_ids": sorted(builder.PRODUCTION_REQUIRED_TEST_SUITES),
                "passed_count": len(builder.PRODUCTION_REQUIRED_TEST_SUITES),
                "failed_count": 0,
                "skipped_count": 0,
                "result_artifact_sha256s": {
                    key: test_digests[key] for key in sorted(test_digests)
                },
            },
        )
        capture_pointers: list[dict[str, str]] = []
        readonly_invocations: list[dict[str, object]] = []
        for index, (invocation_id, query_generation) in enumerate(
            (("capture-a", "query-a"), ("capture-b", "query-b"))
        ):
            capture_account_fingerprint = (
                capture_account_fingerprints[index]
                if capture_account_fingerprints is not None
                else runtime_identity["account_fingerprint"]
            )
            lifecycle = {"proof_complete": 0}
            query_pointers = {
                name: self._private_bytes(
                    bundle,
                    f"raw-stage174-{name}-{index:02d}.artifact",
                    f"{name}-capture-{index}\n".encode("utf-8"),
                )
                for name in ("orders", "trades", "positions")
            }
            stage174 = {
                "source_commit": self.commit,
                "generated_at": f"2026-07-21T13:57:0{index}+08:00",
                "invocation_id": invocation_id,
                "query_generation_uuid": query_generation,
                "broker_trading_day": "20260721",
                "status": "readonly_snapshots_received",
                "order_api_called": False,
                "send_order_api_attempted_count": 0,
                "cancel_order_api_attempted_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "native_mutation_api_attempted_count": 0,
                "native_mutation_api_called_count": 0,
                "order_api_attempted_count": 0,
                "order_api_called_count": 0,
                "broker_snapshot": {
                    "position_snapshot_state": "confirmed_flat"
                },
                "connection_lifecycle": lifecycle,
                "broker_query_bundle": {
                    "complete": True,
                    "generation_uuid": query_generation,
                    "broker_trading_day": "20260721",
                    "full_snapshot_current_generation": True,
                    "trade_order_join_complete": True,
                    "trade_identity_complete": True,
                    "account": {
                        "account_fingerprint": capture_account_fingerprint,
                        "login_account_match": True,
                        "response_account_match": True,
                        "trading_account_response_match": True,
                    },
                    "queries": {
                        name: {"complete": True}
                        for name in (
                            "account",
                            "positions",
                            "orders",
                            "trades",
                            "contracts",
                        )
                    },
                    "artifacts": {
                        name: {
                            "row_generation_match": True,
                            "row_account_match": True,
                            "sha256": query_pointers[name]["artifact_sha256"],
                            "row_count": 0,
                        }
                        for name in ("orders", "trades", "positions")
                    },
                },
            }
            stage174_pointer = self._private_json(
                bundle,
                f"raw-stage174-summary-{index:02d}.json",
                stage174,
            )
            stage174_digest = builder._raw_summary_canonical_sha256(stage174)
            stage907 = {
                "source_commit": self.commit,
                "stage174_source_commit": self.commit,
                "mode": "refresh",
                "env_profile": "production-live",
                "official_live_version": C9_15W_PROFILE.official_version,
                "refresh_status": "readonly_refresh_completed_snapshot_ready",
                "refresh_attempted": 1,
                "command_exit_code": 0,
                "blocking_failure_count": 0,
                "readonly_status_after": "readonly_snapshots_received",
                "position_snapshot_state_after": "confirmed_flat",
                "order_api_evidence_complete": 1,
                "order_api_evidence_missing_fields": [],
                "order_api_evidence_nonzero_fields": [],
                "snapshot_evidence_complete": 1,
                "snapshot_evidence_missing_fields": [],
                "broker_query_bundle_complete": True,
                "stage174_invocation_id": invocation_id,
                "snapshot_generation_uuid": query_generation,
                "stage174_file_summary_sha256": stage174_digest,
                "stage174_stdout_summary_sha256": stage174_digest,
                "stage174_stdout_file_payload_match": 1,
                "connection_lifecycle": lifecycle,
                "sanitized_command_plan": (
                    "source /stable/ctp_live.local.env\n"
                    "export DYLD_FRAMEWORK_PATH=/stable/.py311/lib/python3.11/"
                    "site-packages/vnpy_ctp/api/libs:/stable/.py311/lib\n"
                    f"python run_ctp_stage174_readonly_probe.py --invocation-id {invocation_id}"
                ),
                "send_order_api_attempted_count": 0,
                "cancel_order_api_attempted_count": 0,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "native_mutation_api_attempted_count": 0,
                "native_mutation_api_called_count": 0,
                "order_api_attempted_count": 0,
                "order_api_called_count": 0,
            }
            stage907_pointer = self._private_json(
                bundle,
                f"raw-stage907-summary-{index:02d}.json",
                stage907,
            )
            stage907_stdout_pointer = self._private_json(
                bundle,
                f"raw-stage907-stdout-{index:02d}.json",
                stage907,
            )
            derived_capture = builder.derive_formal_ctp_readonly_capture(
                stage907_summary=stage907,
                stage174_summary=stage174,
                source_commit=self.commit,
                stage907_summary_artifact=stage907_pointer,
                stage174_summary_artifact=stage174_pointer,
                stage907_stdout_artifact=stage907_stdout_pointer,
                query_artifacts=query_pointers,
                env_identity_sha256=runtime_identity["env_identity_sha256"],
                formal_framework_realpaths=runtime_identity[
                    "formal_framework_realpaths"
                ],
                python_sha256=runtime_identity["python_sha256"],
                vnpy_ctp_extension_sha256s=runtime_identity[
                    "vnpy_ctp_extension_sha256s"
                ],
                formal_framework_executable_sha256s=runtime_identity[
                    "formal_framework_executable_sha256s"
                ],
            )
            capture_pointers.append(
                self._private_json(
                    bundle,
                    f"derived-readonly-capture-{index:02d}.json",
                    derived_capture,
                )
            )
            readonly_invocations.append(
                {
                    "capture_index": index,
                    "invocation_nonce": f"{100 + index:032x}",
                    "argv": [
                        runtime_identity["python_realpath"],
                        str(
                            Path(runtime_identity["cwd_realpath"])
                            / "examples/portfolio_backtesting/"
                            "run_qmt_roll_stage907_official_live_readonly_refresh_gate.py"
                        ),
                        "--mode",
                        "refresh",
                        "--env-profile",
                        "production-live",
                        "--wait-seconds",
                        "30",
                        "--confirm-readonly-refresh",
                        "I_UNDERSTAND_THIS_RUNS_CTP_READONLY_REFRESH_ONLY",
                        "--email-policy",
                        "never",
                    ],
                    "python_realpath": runtime_identity["python_realpath"],
                    "python_sha256": runtime_identity["python_sha256"],
                    "vnpy_ctp_extension_sha256s": runtime_identity[
                        "vnpy_ctp_extension_sha256s"
                    ],
                    "formal_framework_executable_sha256s": runtime_identity[
                        "formal_framework_executable_sha256s"
                    ],
                    "cwd_realpath": runtime_identity["cwd_realpath"],
                    "started_at_utc": "2026-07-21T05:57:00Z",
                    "finished_at_utc": "2026-07-21T05:57:10Z",
                    "returncode": 0,
                    "stage907_summary_sha256": stage907_pointer[
                        "artifact_sha256"
                    ],
                    "stage174_summary_sha256": stage174_pointer[
                        "artifact_sha256"
                    ],
                    "stage907_stdout_sha256": stage907_stdout_pointer[
                        "artifact_sha256"
                    ],
                    "account_fingerprint": capture_account_fingerprint,
                    "env_identity_sha256": runtime_identity[
                        "env_identity_sha256"
                    ],
                    "formal_framework_realpaths": runtime_identity[
                        "formal_framework_realpaths"
                    ],
                    "python_sha256": runtime_identity["python_sha256"],
                    "vnpy_ctp_extension_sha256s": runtime_identity[
                        "vnpy_ctp_extension_sha256s"
                    ],
                    "formal_framework_executable_sha256s": runtime_identity[
                        "formal_framework_executable_sha256s"
                    ],
                    "query_artifact_sha256s": {
                        name: query_pointers[name]["artifact_sha256"]
                        for name in ("orders", "trades", "positions")
                    },
                    "environment_sha256": runner_environment_receipts[
                        "readonly"
                    ]["environment_sha256"],
                }
            )
        readonly_pointer = self._private_json(
            bundle,
            "formal-ctp-readonly.json",
            {
                "schema_version": 1,
                "artifact_kind": "formal_ctp_readonly_qualification",
                "status": "qualified",
                "runtime_profile": "production-readonly",
                "env_profile": "ctp_live.local.env",
                "source_commit": self.commit,
                "generated_at_utc": "2026-07-21T05:58:00Z",
                "capture_count": 2,
                "capture_invocation_ids": ["capture-a", "capture-b"],
                "capture_query_generations": ["query-a", "query-b"],
                "broker_trading_day": "20260721",
                "account_fingerprint": runtime_identity[
                    "account_fingerprint"
                ],
                "env_identity_sha256": runtime_identity[
                    "env_identity_sha256"
                ],
                "formal_framework_realpaths": runtime_identity[
                    "formal_framework_realpaths"
                ],
                "python_sha256": runtime_identity["python_sha256"],
                "vnpy_ctp_extension_sha256s": runtime_identity[
                    "vnpy_ctp_extension_sha256s"
                ],
                "formal_framework_executable_sha256s": runtime_identity[
                    "formal_framework_executable_sha256s"
                ],
                "query_bundle_complete": 1,
                "account_query_complete": 1,
                "position_query_complete": 1,
                "order_query_complete": 1,
                "trade_query_complete": 1,
                "warm_disconnect_reconnect_fault_tests_passed": 1,
                "natural_disconnect_reconnect_proof_observed": 0,
                "capture_artifacts": capture_pointers,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
            },
        )
        evidence: dict[str, object] = {
            "schema_version": builder.PRODUCTION_QUALIFICATION_SCHEMA_VERSION,
            "evidence_kind": builder.PRODUCTION_QUALIFICATION_EVIDENCE_KIND,
            "generated_at_utc": "2026-07-21T05:59:00Z",
            "source_commit": self.commit,
            "execution_profile": C9_15W_PROFILE.profile_key,
            "official_version": C9_15W_PROFILE.official_version,
            "capital": C9_15W_PROFILE.capital,
            "capital_label": C9_15W_PROFILE.capital_label,
            "critical_files": rows,
            "tree_fingerprint": tree,
            "review": review_pointer,
            "required_tests": test_pointers,
            "selected_suite_aggregate": aggregate_pointer,
            "formal_ctp_readonly": readonly_pointer,
            "trusted_runner": {
                "schema_version": 1,
                "artifact_kind": "production_qualification_runner_receipt",
                "runner_mode": "trusted_subprocess_v1",
                "source_commit": self.commit,
                "tree_fingerprint": tree,
                "python_realpath": runtime_identity["python_realpath"],
                "python_sha256": runtime_identity["python_sha256"],
                "vnpy_ctp_extension_sha256s": runtime_identity[
                    "vnpy_ctp_extension_sha256s"
                ],
                "formal_framework_executable_sha256s": runtime_identity[
                    "formal_framework_executable_sha256s"
                ],
                "formal_framework_realpaths": runtime_identity[
                    "formal_framework_realpaths"
                ],
                "cwd_realpath": runtime_identity["cwd_realpath"],
                "run_nonce": "f" * 32,
                "started_at_utc": "2026-07-21T05:55:00Z",
                "finished_at_utc": "2026-07-21T05:58:00Z",
                "pytest_environment": runner_environment_receipts["pytest"],
                "readonly_environment": runner_environment_receipts[
                    "readonly"
                ],
                "pytest_invocations": pytest_invocations,
                "readonly_invocations": readonly_invocations,
            },
        }
        evidence["evidence_sha256"] = (
            builder.production_qualification_evidence_digest(evidence)
        )
        evidence_path = bundle / "qualification.json"
        evidence_path.write_bytes(
            builder.serialize_production_qualification_evidence(evidence)
        )
        evidence_path.chmod(0o600)
        return evidence_path, evidence

    def _reseal_production_evidence(
        self,
        evidence_path: Path,
        evidence: dict[str, object],
    ) -> None:
        evidence["evidence_sha256"] = (
            builder.production_qualification_evidence_digest(evidence)
        )
        evidence_path.write_bytes(
            builder.serialize_production_qualification_evidence(evidence)
        )
        evidence_path.chmod(0o600)

    def _validate_production_evidence(
        self,
        evidence_path: Path,
        *,
        critical_files: tuple[str, ...],
    ) -> dict[str, object]:
        return builder.load_and_validate_production_qualification_evidence(
            evidence_path,
            repo_root=self.repo,
            source_commit=self.commit,
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=critical_files,
            manifest_created_at_utc="2026-07-21T06:00:00Z",
        )

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
            "examples/portfolio_backtesting/run_qmt_roll_stage907_official_live_readonly_refresh_gate.py",
            "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py",
            "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh",
            "examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py",
            "examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py",
            "examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py",
            "examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py",
            "examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py",
            "examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py",
            "examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py",
            "examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
            "examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py",
            "examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py",
            "examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py",
            "examples/portfolio_backtesting/qmt_roll_official_candidate_stage847_c9_config.py",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-readonly-day-session.plist",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-readonly-night-session.plist",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-direct.plist",
            "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-supervisor.plist",
            "tests/stage179_performance_gate.py",
            "tests/test_stage179_performance_gate_diagnostics.py",
            "tests/test_stage179_production_performance_gate.py",
            "tests/test_stage179_readonly_canary_qualification.py",
            "tests/test_stage907_readonly_refresh_gate.py",
            "tests/test_stage608_continuous_tick_stream.py",
            "tests/test_stage930_fast_lane.py",
            "tests/test_stage934_readonly_health_check.py",
            "tests/test_official_live_failure_notify.py",
            "tests/test_official_live_config_import.py",
        }

        self.assertTrue(required.issubset(set(builder.DEFAULT_CRITICAL_FILES)))
        self.assertIn(
            "tests/test_official_live_failure_notify.py",
            builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )
        self.assertIn(
            "tests/test_official_live_config_import.py",
            builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )

    def test_postclose_pipeline_is_pinned_in_production_release_surface(self) -> None:
        self.assertIn(
            "examples/portfolio_backtesting/qmt_roll_official_live_postclose_pipeline.py",
            builder.DEFAULT_CRITICAL_FILES,
        )
        self.assertIn(
            "tests/test_official_live_postclose_pipeline.py",
            builder.DEFAULT_CRITICAL_FILES,
        )
        self.assertIn(
            "tests/test_official_live_postclose_pipeline.py",
            builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )

    def test_stage935_path_consistency_is_pinned_in_production_release_surface(
        self,
    ) -> None:
        suite = "tests/test_stage935_ai_pool_path_consistency.py"
        self.assertIn(suite, builder.DEFAULT_CRITICAL_FILES)
        self.assertIn(suite, builder.PRODUCTION_REQUIRED_TEST_SUITES)

    def test_strategy_material_toolchain_is_pinned_in_production_release_surface(
        self,
    ) -> None:
        required_files = {
            "examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py",
            "examples/portfolio_backtesting/qmt_roll_strategy_material_discovery.py",
            "examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py",
            "examples/portfolio_backtesting/qmt_roll_ai_artifact_registry.py",
            "tests/test_strategy_material_manifest.py",
            "tests/test_strategy_material_discovery.py",
            "tests/test_official_strategy_material_release.py",
            "tests/test_ai_artifact_registry.py",
            "examples/portfolio_backtesting/qmt_roll_official_strategy_material_resolver.py",
            "tests/test_official_strategy_material_resolver.py",
            "skills/freeze-official-strategy-materials/SKILL.md",
            "skills/freeze-official-strategy-materials/references/material-contract.md",
            "skills/freeze-official-strategy-materials/agents/openai.yaml",
        }
        self.assertTrue(required_files.issubset(set(builder.DEFAULT_CRITICAL_FILES)))
        self.assertTrue(
            {
                "tests/test_official_strategy_material_release.py",
                "tests/test_ai_artifact_registry.py",
            }.issubset(set(builder.PRODUCTION_REQUIRED_TEST_SUITES))
        )

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
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline",),
                created_at_utc="2026-07-18T11:00:00Z",
            )

        dirty.unlink()

        default_output = Path(self.tempdir.name) / "default-built-release.json"
        readonly_default = build_release_manifest_file(
            output_path=default_output,
            repo_root=self.repo,
            release_id="readonly-default",
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=("a.py", "b.json"),
            created_at_utc="2026-07-18T11:00:00Z",
        )
        self.assertEqual(
            ["offline", "production-readonly"],
            readonly_default["allowed_runtime_profiles"],
        )

        first = build_release_manifest_file(
            output_path=output,
            repo_root=self.repo,
            release_id="r1",
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=("a.py", "b.json"),
            allowed_runtime_profiles=("offline",),
            created_at_utc="2026-07-18T11:00:00Z",
        )
        same = build_release_manifest_file(
            output_path=output,
            repo_root=self.repo,
            release_id="r1",
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
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
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline",),
                created_at_utc="2026-07-18T11:00:00Z",
            )

    def test_builder_allows_c9_production_live_only_with_external_evidence_bundle(self) -> None:
        output = Path(self.tempdir.name) / "c9-production-release.json"
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )
        evidence_path, evidence = self._production_evidence(
            critical_files=critical_files,
        )
        payload = build_release_manifest_file(
            output_path=output,
            repo_root=self.repo,
            release_id="c9-production",
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=critical_files,
            allowed_runtime_profiles=(
                "offline",
                "production-readonly",
                "production-live",
            ),
            production_qualification_evidence=evidence_path,
            created_at_utc="2026-07-21T06:00:00Z",
        )
        self.assertIn("production-live", payload["allowed_runtime_profiles"])
        self.assertEqual(
            "passed",
            payload["strategy_semantics_qualification"]["status"],
        )
        self.assertEqual(
            evidence["evidence_sha256"],
            payload["strategy_semantics_qualification"]["evidence_id"],
        )
        loaded = load_and_validate_release_manifest(
            output,
            repo_root=self.repo,
            expected_official_version=C9_15W_PROFILE.official_version,
            expected_capital=C9_15W_PROFILE.capital,
            expected_capital_label=C9_15W_PROFILE.capital_label,
            expected_execution_profile=C9_15W_PROFILE.profile_key,
            required_runtime_profile="production-live",
            current_commit=self._git("rev-parse", "HEAD").stdout.strip(),
        )
        self.assertEqual(payload["manifest_sha256"], loaded["manifest_sha256"])

    def test_trusted_wrapper_assembles_patch_runner_private_artifacts(self) -> None:
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )
        source_evidence_path, source_evidence = self._production_evidence(
            critical_files=critical_files,
        )
        source_bundle = source_evidence_path.parent
        review_summary = json.loads(
            (
                source_bundle
                / source_evidence["review"]["artifact_path"]
            ).read_text(encoding="utf-8")
        )
        test_summaries = {
            row["suite_id"]: json.loads(
                (source_bundle / row["artifact_path"]).read_text(encoding="utf-8")
            )
            for row in source_evidence["required_tests"]
        }
        readonly_summary = json.loads(
            (
                source_bundle
                / source_evidence["formal_ctp_readonly"]["artifact_path"]
            ).read_text(encoding="utf-8")
        )
        capture_payloads = [
            json.loads(
                (source_bundle / pointer["artifact_path"]).read_text(
                    encoding="utf-8"
                )
            )
            for pointer in readonly_summary["capture_artifacts"]
        ]
        trusted_source = source_evidence["trusted_runner"]
        output_bundle = Path(self.tempdir.name) / "assembled-qualification"
        junit_artifacts = {
            suite_id: source_bundle / summary["junit_artifact_path"]
            for suite_id, summary in test_summaries.items()
        }
        exit_artifacts = {
            suite_id: source_bundle / summary["exit_status_artifact_path"]
            for suite_id, summary in test_summaries.items()
        }
        readonly_captures = [
            {
                "stage907": source_bundle
                / capture["stage907_summary_artifact"]["artifact_path"],
                "stage174": source_bundle
                / capture["stage174_summary_artifact"]["artifact_path"],
                "stage907_stdout": source_bundle
                / capture["stage907_stdout_artifact"]["artifact_path"],
                **{
                    name: source_bundle
                    / capture["query_artifacts"][name]["artifact_path"]
                    for name in ("orders", "trades", "positions")
                },
            }
            for capture in capture_payloads
        ]
        pytest_invocations = [
            {
                **row,
                "output_path": source_bundle / row["output_artifact_path"],
            }
            for row in trusted_source["pytest_invocations"]
        ]
        with (
            patch.object(
                bundle_builder,
                "_run_trusted_pytest_inputs",
                return_value=(
                    junit_artifacts,
                    exit_artifacts,
                    pytest_invocations,
                    trusted_source["pytest_environment"],
                ),
            ),
            patch.object(
                bundle_builder,
                "_run_trusted_readonly_inputs",
                return_value=(
                    readonly_captures,
                    trusted_source["readonly_invocations"],
                    trusted_source["readonly_environment"],
                ),
            ),
            patch.object(
                bundle_builder,
                "_utc_now",
                side_effect=(
                    "2026-07-21T05:55:00Z",
                    "2026-07-21T05:58:00Z",
                ),
            ),
        ):
            assembled = (
                bundle_builder.build_trusted_production_qualification_bundle(
                    output_dir=output_bundle,
                    repo_root=self.repo,
                    review_report=(
                        source_bundle
                        / review_summary["report_artifact_path"]
                    ),
                    confirmation=(
                        bundle_builder.PRODUCTION_QUALIFICATION_RUN_CONFIRM_TEXT
                    ),
                    critical_files=critical_files,
                    generated_at_utc="2026-07-21T05:59:00Z",
                )
            )

        self.assertEqual(output_bundle / "qualification.json", assembled)
        self.assertEqual(0o700, output_bundle.stat().st_mode & 0o777)
        self.assertTrue(
            all(
                (path.stat().st_mode & 0o777) == 0o600
                for path in output_bundle.iterdir()
            )
        )
        loaded = builder.load_and_validate_production_qualification_evidence(
            assembled,
            repo_root=self.repo,
            source_commit=self.commit,
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            critical_files=critical_files,
            manifest_created_at_utc="2026-07-21T06:00:00Z",
        )
        self.assertEqual(
            json.loads(assembled.read_text(encoding="utf-8"))["evidence_sha256"],
            loaded["evidence_sha256"],
        )

    def test_low_level_bundle_assembler_requires_process_local_capability(
        self,
    ) -> None:
        self.assertFalse(
            hasattr(bundle_builder, "build_production_qualification_bundle")
        )
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "production_bundle_trusted_assembler_capability_missing",
        ):
            bundle_builder._assemble_production_qualification_bundle(
                output_dir=Path(self.tempdir.name) / "never-created",
                repo_root=self.repo,
                review_report=Path(self.tempdir.name) / "never-read.json",
                pytest_junit_artifacts={},
                pytest_exit_status_artifacts={},
                formal_ctp_readonly_raw_captures=[],
                trusted_runner_context={},
                critical_files=("a.py", "b.json"),
                _trusted_assembler_sentinel=object(),
            )

    def test_runtime_identity_hashes_python_ctp_extensions_and_frameworks(
        self,
    ) -> None:
        identity = builder._production_runtime_identity(self.repo)

        self.assertRegex(identity["python_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            {"vnctpmd", "vnctptd"},
            set(identity["vnpy_ctp_extension_sha256s"]),
        )
        self.assertEqual(
            {"thostmduserapi_se", "thosttraderapi_se"},
            set(identity["formal_framework_executable_sha256s"]),
        )
        for digest in (
            *identity["vnpy_ctp_extension_sha256s"].values(),
            *identity["formal_framework_executable_sha256s"].values(),
        ):
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "runtime_binary_missing:fixture",
        ):
            builder._runtime_file_sha256(
                self.repo / "missing-runtime-binary",
                identity="fixture",
            )

    def test_qualification_validation_recomputes_runtime_binary_hashes(
        self,
    ) -> None:
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )
        evidence_path, _evidence = self._production_evidence(
            critical_files=critical_files,
        )
        drifted = copy.deepcopy(builder._production_runtime_identity(self.repo))
        drifted["vnpy_ctp_extension_sha256s"]["vnctptd"] = "9" * 64

        with (
            patch.object(
                builder,
                "_production_runtime_identity",
                return_value=drifted,
            ),
            self.assertRaisesRegex(
                ReleaseManifestError,
                "production_trusted_runner_invalid",
            ),
        ):
            self._validate_production_evidence(
                evidence_path,
                critical_files=critical_files,
            )

    def test_trusted_pytest_runner_spawns_exact_command_with_minimal_environment(
        self,
    ) -> None:
        suite_id = "tests/test_trusted_runner_probe.py"
        probe = self.repo / suite_id
        probe.write_text(
            "def test_trusted_runner_probe():\n    assert True\n",
            encoding="utf-8",
        )
        self._git("add", suite_id)
        self._git("commit", "-m", "trusted runner probe")
        source_commit = self._git("rev-parse", "HEAD").stdout.strip()
        runtime_identity = builder._production_runtime_identity(self.repo)
        staging = Path(self.tempdir.name) / "trusted-runner-staging"
        staging.mkdir(mode=0o700)
        injected = {
            "PYTHONPATH": "/malicious/pythonpath",
            "PYTEST_ADDOPTS": "--collect-only",
            "CTP_PASSWORD": "must-not-propagate",
            "OFFICIAL_LIVE_OUTPUT_DIR": "/malicious/live-output",
            builder.TRUSTED_RUNNER_READONLY_GATE_ENV: "caller-value",
        }
        with (
            patch.dict(os.environ, injected, clear=False),
            patch.object(
                bundle_builder,
                "PRODUCTION_REQUIRED_TEST_SUITES",
                (suite_id,),
            ),
        ):
            junit_paths, exit_paths, invocations, pytest_environment = (
                bundle_builder._run_trusted_pytest_inputs(
                    repo=self.repo.resolve(strict=True),
                    source_commit=source_commit,
                    staging=staging,
                    runtime_identity=runtime_identity,
                )
            )

        self.assertEqual(b"0\n", exit_paths[suite_id].read_bytes())
        self.assertEqual(
            {"passed_count": 1, "failed_count": 0, "skipped_count": 0},
            builder._junit_counts(
                junit_paths[suite_id].read_bytes(),
                suite_id=suite_id,
            ),
        )
        row = invocations[0]
        self.assertEqual(runtime_identity["python_realpath"], row["argv"][0])
        self.assertEqual(suite_id, row["argv"][4])
        self.assertEqual(
            builder.PRODUCTION_DIRECT_SCHEDULER_POLICY,
            row["scheduler_policy"],
        )
        self.assertNotIn(
            builder.PRODUCTION_PERFORMANCE_TASKPOLICY_PATH,
            row["argv"],
        )
        self.assertEqual(
            pytest_environment["environment_sha256"],
            row["environment_sha256"],
        )
        self.assertEqual(
            list(builder.TRUSTED_RUNNER_BASE_ENVIRONMENT_KEYS),
            pytest_environment["allowlist_keys"],
        )
        self.assertEqual("none", pytest_environment["credential_source"])

        readonly_environment, readonly_receipt = (
            bundle_builder._runner_owned_environment(
                staging=staging,
                readonly=True,
            )
        )
        self.assertEqual(
            set(builder.TRUSTED_RUNNER_READONLY_ENVIRONMENT_KEYS),
            set(readonly_environment),
        )
        self.assertEqual(
            "1",
            readonly_environment[builder.TRUSTED_RUNNER_READONLY_GATE_ENV],
        )
        self.assertFalse(
            any(key.startswith("CTP_") for key in readonly_environment)
        )
        self.assertEqual(
            [builder.TRUSTED_RUNNER_READONLY_GATE_ENV],
            [
                key
                for key in readonly_environment
                if key.startswith("OFFICIAL_LIVE_")
            ],
        )
        self.assertEqual(
            "repo-private-ctp_live.local.env",
            readonly_receipt["credential_source"],
        )
        receipt_bytes = builder.serialize_production_qualification_evidence(
            readonly_receipt
        )
        self.assertNotIn(b"must-not-propagate", receipt_bytes)
        self.assertNotIn(b"test-account", receipt_bytes)

    def test_performance_suite_uses_exact_absolute_taskpolicy_wrapper(
        self,
    ) -> None:
        suite_id = builder.PRODUCTION_PERFORMANCE_TEST_SUITE
        staging = Path(self.tempdir.name) / "performance-runner-staging"
        staging.mkdir(mode=0o700)
        runtime_identity = builder._production_runtime_identity(self.repo)
        observed_argv: list[str] = []

        def passing_runner(argv: list[str], **_kwargs: object) -> object:
            observed_argv[:] = argv
            junit_argument = next(
                value for value in argv if value.startswith("--junitxml=")
            )
            Path(junit_argument.split("=", 1)[1]).write_text(
                f'<testsuites><testsuite name="{suite_id}">'
                '<testcase classname="production" name="passes" />'
                "</testsuite></testsuites>\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(argv, 0, stdout=b"passed\n")

        with patch.object(
            bundle_builder,
            "PRODUCTION_REQUIRED_TEST_SUITES",
            (suite_id,),
        ):
            _junit, _exit, invocations, _environment = (
                bundle_builder._run_trusted_pytest_inputs(
                    repo=self.repo.resolve(strict=True),
                    source_commit=self.commit,
                    staging=staging,
                    runtime_identity=runtime_identity,
                    runner=passing_runner,
                )
            )

        expected_prefix = [
            builder.PRODUCTION_PERFORMANCE_TASKPOLICY_PATH,
            "-a",
            runtime_identity["python_realpath"],
            "-m",
            "pytest",
            "-q",
            suite_id,
        ]
        self.assertEqual(expected_prefix, observed_argv[:7])
        self.assertEqual(
            [
                "-o",
                f"junit_suite_name={suite_id}",
                "-p",
                "no:cacheprovider",
            ],
            observed_argv[8:],
        )
        self.assertTrue(observed_argv[7].startswith("--junitxml="))
        self.assertEqual(
            builder.PRODUCTION_PERFORMANCE_SCHEDULER_POLICY,
            invocations[0]["scheduler_policy"],
        )

    def test_performance_taskpolicy_preconditions_fail_closed(self) -> None:
        kwargs = {
            "suite_id": builder.PRODUCTION_PERFORMANCE_TEST_SUITE,
            "python_realpath": str(Path(sys.executable).resolve()),
            "junit_path": Path(self.tempdir.name) / "result.xml",
        }
        with (
            patch.object(bundle_builder.platform, "system", return_value="Linux"),
            self.assertRaisesRegex(
                ReleaseManifestError,
                "performance_taskpolicy_platform_invalid",
            ),
        ):
            bundle_builder._trusted_pytest_argv(**kwargs)
        with (
            patch.object(bundle_builder.platform, "system", return_value="Darwin"),
            patch.object(
                bundle_builder,
                "PRODUCTION_PERFORMANCE_TASKPOLICY_PATH",
                str(Path(self.tempdir.name) / "missing-taskpolicy"),
            ),
            self.assertRaisesRegex(
                ReleaseManifestError,
                "performance_taskpolicy_missing_or_invalid",
            ),
        ):
            bundle_builder._trusted_pytest_argv(**kwargs)

    def test_production_qualification_cli_rejects_external_test_artifacts(
        self,
    ) -> None:
        for flag, value in (
            ("--pytest-junit", "caller-controlled.xml"),
            ("--pytest-exit-status", "caller-controlled.exit"),
            ("--formal-ctp-readonly-capture", "caller-controlled.json"),
            ("--critical-file", "caller-reduced-scope.py"),
            ("--generated-at-utc", "2099-01-01T00:00:00Z"),
        ):
            with self.subTest(flag=flag):
                argv = [
                    str(bundle_builder.__file__),
                    "--output-dir",
                    str(Path(self.tempdir.name) / "never-created"),
                    "--review-report",
                    str(Path(self.tempdir.name) / "never-read.json"),
                    "--confirm-trusted-production-qualification-run",
                    bundle_builder.PRODUCTION_QUALIFICATION_RUN_CONFIRM_TEXT,
                    flag,
                    value,
                ]
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(
                        bundle_builder,
                        "build_trusted_production_qualification_bundle",
                        side_effect=AssertionError("runner must not start"),
                    ),
                    patch("sys.stderr", new=io.StringIO()) as stderr,
                ):
                    with self.assertRaises(SystemExit) as raised:
                        bundle_builder.main()
                self.assertEqual(2, raised.exception.code)
                self.assertIn(
                    f"unrecognized arguments: {flag}",
                    stderr.getvalue(),
                )

    def test_trusted_orchestrator_never_reaches_readonly_after_test_failure(
        self,
    ) -> None:
        with (
            patch.object(
                bundle_builder,
                "_run_trusted_pytest_inputs",
                side_effect=ReleaseManifestError(
                    "production_bundle_runner_pytest_failed:fixture"
                ),
            ),
            patch.object(
                bundle_builder,
                "_run_trusted_readonly_inputs",
            ) as readonly_runner,
        ):
            with self.assertRaisesRegex(
                ReleaseManifestError,
                "production_bundle_runner_pytest_failed",
            ):
                bundle_builder.build_trusted_production_qualification_bundle(
                    output_dir=Path(self.tempdir.name) / "never-published",
                    repo_root=self.repo,
                    review_report=Path(self.tempdir.name) / "never-read.json",
                    confirmation=(
                        bundle_builder.PRODUCTION_QUALIFICATION_RUN_CONFIRM_TEXT
                    ),
                    critical_files=("a.py", "b.json"),
                )
        readonly_runner.assert_not_called()

    def test_trusted_pytest_runner_rejects_real_nonzero_receipt(self) -> None:
        suite_id = builder.PRODUCTION_REQUIRED_TEST_SUITES[0]
        staging = Path(self.tempdir.name) / "failed-runner-staging"
        staging.mkdir(mode=0o700)
        runtime_identity = builder._production_runtime_identity(self.repo)

        def failing_runner(argv: list[str], **_kwargs: object) -> object:
            junit_path = Path(argv[5].split("=", 1)[1])
            junit_path.write_text(
                f'<testsuites><testsuite name="{suite_id}">'
                '<testcase classname="production" name="fails">'
                '<failure message="fixture" />'
                "</testcase></testsuite></testsuites>\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(
                argv,
                1,
                stdout=b"one failed\n",
            )

        with patch.object(
            bundle_builder,
            "PRODUCTION_REQUIRED_TEST_SUITES",
            (suite_id,),
        ):
            with self.assertRaisesRegex(
                ReleaseManifestError,
                "production_bundle_runner_pytest_failed",
            ):
                bundle_builder._run_trusted_pytest_inputs(
                    repo=self.repo.resolve(strict=True),
                    source_commit=self.commit,
                    staging=staging,
                    runtime_identity=runtime_identity,
                    runner=failing_runner,
                )
        self.assertEqual(
            b"1\n",
            (staging / "raw-pytest-00.exit-status").read_bytes(),
        )
        self.assertEqual(
            b"one failed\n",
            (staging / "raw-pytest-00.output").read_bytes(),
        )

    def test_trusted_runner_receipt_tampering_is_rejected(self) -> None:
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )

        def assert_rejected(mutation: str, expected: str) -> None:
            evidence_path, evidence = self._production_evidence(
                critical_files=critical_files,
            )
            trusted = evidence["trusted_runner"]
            if mutation == "allowlist":
                trusted["pytest_environment"]["allowlist_keys"].append(
                    "PYTEST_ADDOPTS"
                )
            elif mutation == "environment_hash":
                trusted["pytest_invocations"][0]["environment_sha256"] = (
                    "0" * 64
                )
            elif mutation == "argv":
                trusted["pytest_invocations"][0]["argv"].extend(
                    ["-k", "caller-filter"]
                )
            elif mutation == "performance_taskpolicy":
                performance_row = next(
                    row
                    for row in trusted["pytest_invocations"]
                    if row["suite_id"]
                    == builder.PRODUCTION_PERFORMANCE_TEST_SUITE
                )
                performance_row["argv"][0] = "/tmp/forged-taskpolicy"
            elif mutation == "performance_scheduler_policy":
                performance_row = next(
                    row
                    for row in trusted["pytest_invocations"]
                    if row["suite_id"]
                    == builder.PRODUCTION_PERFORMANCE_TEST_SUITE
                )
                performance_row["scheduler_policy"] = "direct_v1"
            elif mutation == "returncode":
                trusted["pytest_invocations"][0]["returncode"] = 1
            elif mutation == "output":
                output_path = (
                    evidence_path.parent
                    / trusted["pytest_invocations"][0]["output_artifact_path"]
                )
                output_path.write_bytes(b"tampered output\n")
                output_path.chmod(0o600)
            else:
                test_pointer = evidence["required_tests"][0]
                summary = json.loads(
                    (
                        evidence_path.parent / test_pointer["artifact_path"]
                    ).read_text(encoding="utf-8")
                )
                junit_path = evidence_path.parent / summary["junit_artifact_path"]
                junit_path.write_bytes(b"<tampered/>\n")
                junit_path.chmod(0o600)
            self._reseal_production_evidence(evidence_path, evidence)
            with self.assertRaisesRegex(ReleaseManifestError, expected):
                self._validate_production_evidence(
                    evidence_path,
                    critical_files=critical_files,
                )

        for mutation, expected in (
            ("allowlist", "trusted_runner_environment_invalid"),
            ("environment_hash", "production_evidence_test_failed"),
            ("argv", "production_evidence_test_failed"),
            ("performance_taskpolicy", "production_evidence_test_failed"),
            (
                "performance_scheduler_policy",
                "production_evidence_test_failed",
            ),
            ("returncode", "production_evidence_test_failed"),
            ("output", "artifact_digest_mismatch"),
            ("junit", "artifact_digest_mismatch"),
        ):
            with self.subTest(mutation=mutation):
                assert_rejected(mutation, expected)

    def test_readonly_raw_query_account_and_env_identity_are_bound(self) -> None:
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )
        alternate_account = hashlib.sha256(b"different-account").hexdigest()
        runtime_account = builder._production_runtime_identity(self.repo)[
            "account_fingerprint"
        ]
        evidence_path, _evidence = self._production_evidence(
            critical_files=critical_files,
            capture_account_fingerprints=(runtime_account, alternate_account),
        )
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "readonly_capture_identity_invalid",
        ):
            self._validate_production_evidence(
                evidence_path,
                critical_files=critical_files,
            )

        evidence_path, evidence = self._production_evidence(
            critical_files=critical_files,
        )
        bundle = evidence_path.parent
        readonly_path = bundle / evidence["formal_ctp_readonly"]["artifact_path"]
        readonly = json.loads(readonly_path.read_text(encoding="utf-8"))
        capture_pointer = readonly["capture_artifacts"][0]
        capture_path = bundle / capture_pointer["artifact_path"]
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
        raw_pointer = capture["query_artifacts"]["orders"]
        raw_path = bundle / raw_pointer["artifact_path"]
        tampered_raw = raw_path.read_bytes() + b"tampered\n"
        raw_path.write_bytes(tampered_raw)
        raw_path.chmod(0o600)
        raw_pointer["artifact_sha256"] = hashlib.sha256(tampered_raw).hexdigest()
        capture_raw = builder.serialize_production_qualification_evidence(capture)
        capture_path.write_bytes(capture_raw)
        capture_path.chmod(0o600)
        capture_pointer["artifact_sha256"] = hashlib.sha256(capture_raw).hexdigest()
        readonly_raw = builder.serialize_production_qualification_evidence(readonly)
        readonly_path.write_bytes(readonly_raw)
        readonly_path.chmod(0o600)
        evidence["formal_ctp_readonly"]["artifact_sha256"] = hashlib.sha256(
            readonly_raw
        ).hexdigest()
        self._reseal_production_evidence(evidence_path, evidence)
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "readonly_raw_capture_invalid",
        ):
            self._validate_production_evidence(
                evidence_path,
                critical_files=critical_files,
            )

        evidence_path, _evidence = self._production_evidence(
            critical_files=critical_files,
        )
        env_path = (
            self.repo
            / "examples/portfolio_backtesting/ctp_live.local.env"
        )
        env_path.write_text(
            "export CTP_BROKERID=test-broker\n"
            "export CTP_USERID=changed-account\n",
            encoding="utf-8",
        )
        env_path.chmod(0o600)
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "readonly_incomplete|readonly_capture_invalid",
        ):
            self._validate_production_evidence(
                evidence_path,
                critical_files=critical_files,
            )

    def test_builder_blocks_missing_or_self_declared_production_qualification(self) -> None:
        kwargs = {
            "output_path": Path(self.tempdir.name) / "blocked-production.json",
            "repo_root": self.repo,
            "release_id": "blocked-production",
            "execution_profile": C9_15W_PROFILE.profile_key,
            "official_version": C9_15W_PROFILE.official_version,
            "capital": C9_15W_PROFILE.capital,
            "capital_label": C9_15W_PROFILE.capital_label,
            "critical_files": ("a.py", "b.json"),
            "allowed_runtime_profiles": ("offline", "production-live"),
            "created_at_utc": "2026-07-21T06:00:00Z",
        }
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "production_qualification_evidence_required",
        ):
            build_release_manifest_file(**kwargs)
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "production_self_declared_qualification_forbidden",
        ):
            build_release_manifest_file(
                **kwargs,
                strategy_semantics_qualification={
                    "status": "passed",
                    "evidence_id": "caller-made-this-up",
                },
            )

    def test_builder_rejects_evidence_review_test_and_readonly_failures(self) -> None:
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )

        def assert_mutation_blocked(
            *,
            mutation: str,
            expected_error: str,
        ) -> None:
            evidence_path, evidence = self._production_evidence(
                critical_files=critical_files,
            )
            bundle = evidence_path.parent
            if mutation == "review_p0":
                pointer = evidence["review"]
                artifact_path = bundle / pointer["artifact_path"]
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                artifact["p0_count"] = 1
            elif mutation == "test_failed":
                pointer = evidence["required_tests"][0]
                artifact_path = bundle / pointer["artifact_path"]
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                artifact["status"] = "failed"
                artifact["failed_count"] = 1
            else:
                pointer = evidence["formal_ctp_readonly"]
                artifact_path = bundle / pointer["artifact_path"]
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                artifact["send_order_api_called_count"] = 1
            encoded = builder.serialize_production_qualification_evidence(artifact)
            artifact_path.write_bytes(encoded)
            artifact_path.chmod(0o600)
            pointer["artifact_sha256"] = hashlib.sha256(encoded).hexdigest()
            self._reseal_production_evidence(evidence_path, evidence)
            with self.assertRaisesRegex(ReleaseManifestError, expected_error):
                build_release_manifest_file(
                    output_path=Path(self.tempdir.name) / f"{mutation}.json",
                    repo_root=self.repo,
                    release_id=mutation,
                    execution_profile=C9_15W_PROFILE.profile_key,
                    official_version=C9_15W_PROFILE.official_version,
                    capital=C9_15W_PROFILE.capital,
                    capital_label=C9_15W_PROFILE.capital_label,
                    critical_files=critical_files,
                    allowed_runtime_profiles=("offline", "production-live"),
                    production_qualification_evidence=evidence_path,
                    created_at_utc="2026-07-21T06:00:00Z",
                )

        for mutation, expected_error in (
            ("review_p0", "review_counts_mismatch"),
            ("test_failed", "production_evidence_test_failed"),
            ("readonly_order_api", "readonly_incomplete"),
        ):
            with self.subTest(mutation=mutation):
                assert_mutation_blocked(
                    mutation=mutation,
                    expected_error=expected_error,
                )

    def test_builder_rejects_missing_tampered_or_insecure_bundle_artifact(self) -> None:
        critical_files = (
            "a.py",
            "b.json",
            *builder.PRODUCTION_REQUIRED_TEST_SUITES,
        )
        evidence_path, evidence = self._production_evidence(
            critical_files=critical_files,
        )
        review_path = evidence_path.parent / evidence["review"]["artifact_path"]
        review_path.chmod(0o644)
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "artifact_permissions_invalid|artifact_permissions_too_open",
        ):
            builder.load_and_validate_production_qualification_evidence(
                evidence_path,
                repo_root=self.repo,
                source_commit=self.commit,
                execution_profile=C9_15W_PROFILE.profile_key,
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
                critical_files=critical_files,
                manifest_created_at_utc="2026-07-21T06:00:00Z",
            )

        review_path.chmod(0o600)
        evidence["review"]["artifact_sha256"] = "0" * 64
        self._reseal_production_evidence(evidence_path, evidence)
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "artifact_digest_mismatch",
        ):
            builder.load_and_validate_production_qualification_evidence(
                evidence_path,
                repo_root=self.repo,
                source_commit=self.commit,
                execution_profile=C9_15W_PROFILE.profile_key,
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
                critical_files=critical_files,
                manifest_created_at_utc="2026-07-21T06:00:00Z",
            )

    def test_production_manifest_requires_exact_clean_source_commit(self) -> None:
        payload = build_release_manifest(
            repo_root=self.repo,
            release_id="production-source-binding",
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            strategy_semantics_qualification={
                "status": "passed",
                "evidence_id": "f" * 64,
            },
            source_commit=self.commit,
            critical_files=("a.py", "b.json"),
            allowed_runtime_profiles=("offline", "production-live"),
            created_at_utc="2026-07-21T06:00:00Z",
        )
        write_release_manifest(self.manifest_path, payload)
        (self.repo / "later.txt").write_text("later\n", encoding="utf-8")
        self._git("add", "later.txt")
        self._git("commit", "-m", "later")
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "production_source_commit_mismatch",
        ):
            load_and_validate_release_manifest(
                self.manifest_path,
                repo_root=self.repo,
                expected_official_version=C9_15W_PROFILE.official_version,
                expected_capital=C9_15W_PROFILE.capital,
                expected_capital_label=C9_15W_PROFILE.capital_label,
                expected_execution_profile=C9_15W_PROFILE.profile_key,
                required_runtime_profile="production-live",
                current_commit=self._git("rev-parse", "HEAD").stdout.strip(),
            )

        exact_payload = build_release_manifest(
            repo_root=self.repo,
            release_id="production-dirty-binding",
            execution_profile=C9_15W_PROFILE.profile_key,
            official_version=C9_15W_PROFILE.official_version,
            capital=C9_15W_PROFILE.capital,
            capital_label=C9_15W_PROFILE.capital_label,
            strategy_semantics_qualification={
                "status": "passed",
                "evidence_id": "e" * 64,
            },
            source_commit=self._git("rev-parse", "HEAD").stdout.strip(),
            critical_files=("a.py", "b.json"),
            allowed_runtime_profiles=("offline", "production-live"),
            created_at_utc="2026-07-21T06:01:00Z",
        )
        dirty_manifest = self.write(exact_payload, "production-dirty.json")
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "production_tree_dirty",
        ):
            load_and_validate_release_manifest(
                dirty_manifest,
                repo_root=self.repo,
                expected_official_version=C9_15W_PROFILE.official_version,
                expected_capital=C9_15W_PROFILE.capital,
                expected_capital_label=C9_15W_PROFILE.capital_label,
                expected_execution_profile=C9_15W_PROFILE.profile_key,
                required_runtime_profile="production-live",
                current_commit=self._git("rev-parse", "HEAD").stdout.strip(),
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
                official_version=STAGE372_20W_PROFILE.official_version,
                capital=STAGE372_20W_PROFILE.capital,
                capital_label=STAGE372_20W_PROFILE.capital_label,
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline", "simnow"),
                strategy_semantics_qualification={
                    "status": "passed",
                    "evidence_id": "caller-self-declared",
                },
                created_at_utc="2026-07-18T11:00:00Z",
            )

    def test_builder_rejects_deprecated_c9_historical_profile_key(self) -> None:
        with self.assertRaisesRegex(
            ReleaseManifestError,
            "release_builder_deprecated_execution_profile_forbidden",
        ):
            build_release_manifest_file(
                output_path=Path(self.tempdir.name) / "deprecated-release.json",
                repo_root=self.repo,
                release_id="deprecated",
                execution_profile="c9-15w-historical",
                official_version=C9_15W_PROFILE.official_version,
                capital=C9_15W_PROFILE.capital,
                capital_label=C9_15W_PROFILE.capital_label,
                critical_files=("a.py", "b.json"),
                allowed_runtime_profiles=("offline",),
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
                    official_version=C9_15W_PROFILE.official_version,
                    capital=C9_15W_PROFILE.capital,
                    capital_label=C9_15W_PROFILE.capital_label,
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
            "tests/test_stage931_post_reprice_final_gate.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/provision_qmt_roll_c9_launchd_directories.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/run_qmt_roll_stage946_official_live_production_health_check.py",
            defaults,
        )
        self.assertIn(
            "examples/portfolio_backtesting/qmt_roll_official_live_authorization_lock.py",
            defaults,
        )
        for session in ("day", "night"):
            self.assertIn(
                "examples/portfolio_backtesting/launchd/"
                "local.qmt-roll.official-live.15w.c9-production-live-"
                f"{session}-session.plist",
                defaults,
            )
        for stage in ("902", "903", "904", "905", "927"):
            self.assertTrue(
                any(f"stage{stage}_" in path for path in defaults),
                stage,
            )


if __name__ == "__main__":
    unittest.main()
