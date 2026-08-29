from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from qmt_roll_official_live_execution_ledger import (
    EXECUTION_LEDGER_READER_CAPABILITIES,
    INTENT_FINGERPRINT_VERSION_V2,
    LEDGER_SCHEMA_VERSION,
)
from qmt_roll_official_live_release_manifest import (
    ReleaseManifestError,
    build_release_manifest,
    release_critical_file_rows,
    release_tree_fingerprint,
    serialize_release_manifest,
    write_release_manifest,
)
from qmt_roll_official_live_runtime_profile import ExecutionRuntimeProfile
from qmt_roll_official_execution_profile import (
    C9_15W_PROFILE,
    ExecutionStrategyMode,
    assert_profile_identity,
    resolve_execution_profile,
)


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PRODUCTION_LIVE_MANIFEST_CONFIRM_TEXT = (
    "I_UNDERSTAND_THIS_BUILDS_A_C9_15W_PRODUCTION_LIVE_RELEASE_MANIFEST"
)
DEFAULT_PRODUCTION_DATA_ROOT = (
    Path.home()
    / "Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs"
)
DEFAULT_PRODUCTION_DATA_LINK = (
    Path.home()
    / "Desktop/person/vnpy_production_live/examples/portfolio_backtesting/backtest_outputs"
)
PRODUCTION_QUALIFICATION_SCHEMA_VERSION = 3
PRODUCTION_QUALIFICATION_EVIDENCE_KIND = (
    "stage179_c9_15w_production_qualification"
)
PRODUCTION_QUALIFICATION_MAX_AGE = timedelta(days=7)
PRODUCTION_QUALIFICATION_MAX_FUTURE_SKEW = timedelta(minutes=5)
PRODUCTION_REQUIRED_TEST_SUITES = (
    "tests/test_official_live_c9_detector.py",
    "tests/test_official_live_c9_intraday_state.py",
    "tests/test_official_live_config_import.py",
    "tests/test_official_live_execution_ledger_cycles.py",
    "tests/test_official_live_failure_notify.py",
    "tests/test_official_live_postclose_pipeline.py",
    "tests/test_official_live_intent_spool.py",
    "tests/test_official_live_late_retry_fill.py",
    "tests/test_stage179_executor_serve.py",
    "tests/test_stage179_activation_receipt_builder.py",
    "tests/test_stage179_fault_matrix.py",
    "tests/test_stage179_launchd_lifecycle.py",
    "tests/test_stage179_production_assets.py",
    "tests/test_stage179_release_manifest.py",
    "tests/test_stage179_submit_authorization.py",
    "tests/test_stage179_two_executor_process_race.py",
    "tests/test_stage179_performance_gate_diagnostics.py",
    "tests/test_stage179_production_performance_gate.py",
    "tests/test_stage905_c9_cycle_intents.py",
    "tests/test_stage904_durable_state_integration.py",
    "tests/test_stage927_scope_permits.py",
    "tests/test_stage930_fast_lane.py",
    "tests/test_stage930_persistent_authorization.py",
    "tests/test_stage931_authorization_guard.py",
    "tests/test_stage931_ctp_readiness.py",
    "tests/test_stage931_post_reprice_final_gate.py",
    "tests/test_stage931_trade_fill_accounting.py",
    "tests/test_stage065_top10_fu_formal_ai_bundle.py",
    "tests/test_stage901_official_ai_pool_policy.py",
    "tests/test_stage929_official_ai_pool_policy.py",
    "tests/test_stage935_ai_pool_path_consistency.py",
    "tests/test_official_strategy_material_release.py",
    "tests/test_ai_artifact_registry.py",
    "tests/test_official_strategy_material_resolver.py",
    "tests/test_official_baseline_identity.py",
    "tests/test_official_promotion_closure.py",
    "tests/test_stage945_production_launcher.py",
    "tests/test_stage946_production_health_check.py",
    "tests/test_stage947_production_support_launcher.py",
    "tests/test_stage948_production_installer.py",
)
PRODUCTION_PERFORMANCE_TEST_SUITE = (
    "tests/test_stage179_production_performance_gate.py"
)
PRODUCTION_PERFORMANCE_TASKPOLICY_PATH = "/usr/sbin/taskpolicy"
PRODUCTION_PERFORMANCE_SCHEDULER_POLICY = "darwin_taskpolicy_absolute_v1"
PRODUCTION_DIRECT_SCHEDULER_POLICY = "direct_v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TRUSTED_RUNNER_ENVIRONMENT_POLICY = "minimal_allowlist_v1"
TRUSTED_RUNNER_FIXED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
TRUSTED_RUNNER_READONLY_GATE_ENV = (
    "OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED"
)
TRUSTED_RUNNER_BASE_ENVIRONMENT_KEYS = tuple(
    sorted(
        {
            "HOME",
            "LANG",
            "LC_ALL",
            "PATH",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONHASHSEED",
            "PYTHONNOUSERSITE",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            "TMPDIR",
        }
    )
)
TRUSTED_RUNNER_READONLY_ENVIRONMENT_KEYS = tuple(
    sorted(
        {
            *TRUSTED_RUNNER_BASE_ENVIRONMENT_KEYS,
            TRUSTED_RUNNER_READONLY_GATE_ENV,
        }
    )
)
_TRUSTED_RUNNER_FIXED_ENVIRONMENT_VALUES = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": TRUSTED_RUNNER_FIXED_PATH,
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
}
_PRODUCTION_EVIDENCE_FIELDS = {
    "schema_version",
    "evidence_kind",
    "generated_at_utc",
    "source_commit",
    "execution_profile",
    "official_version",
    "capital",
    "capital_label",
    "critical_files",
    "tree_fingerprint",
    "review",
    "required_tests",
    "selected_suite_aggregate",
    "formal_ctp_readonly",
    "trusted_runner",
    "evidence_sha256",
}
_ARTIFACT_POINTER_FIELDS = {"artifact_path", "artifact_sha256"}
_TEST_ARTIFACT_POINTER_FIELDS = {
    "suite_id",
    "artifact_path",
    "artifact_sha256",
}
_PRODUCTION_REVIEW_ARTIFACT_FIELDS = {
    "schema_version",
    "artifact_kind",
    "review_kind",
    "review_id",
    "reviewer_identity",
    "reviewed_at_utc",
    "source_commit",
    "tree_fingerprint",
    "p0_count",
    "p1_count",
    "p2_count",
    "report_artifact_path",
    "report_artifact_sha256",
}
_PRODUCTION_REVIEW_REPORT_FIELDS = {
    "schema_version",
    "artifact_kind",
    "review_id",
    "reviewer_identity",
    "reviewed_at_utc",
    "source_commit",
    "tree_fingerprint",
    "findings",
}
_PRODUCTION_REVIEW_FINDING_FIELDS = {
    "finding_id",
    "severity",
    "status",
}
_PRODUCTION_TEST_ARTIFACT_FIELDS = {
    "schema_version",
    "artifact_kind",
    "suite_id",
    "status",
    "passed_count",
    "failed_count",
    "skipped_count",
    "source_commit",
    "tree_fingerprint",
    "test_file_sha256",
    "generated_at_utc",
    "pytest_exit_code",
    "exit_status_artifact_path",
    "exit_status_artifact_sha256",
    "junit_artifact_path",
    "junit_artifact_sha256",
}
_PRODUCTION_TEST_AGGREGATE_ARTIFACT_FIELDS = {
    "schema_version",
    "artifact_kind",
    "status",
    "source_commit",
    "tree_fingerprint",
    "generated_at_utc",
    "suite_ids",
    "passed_count",
    "failed_count",
    "skipped_count",
    "result_artifact_sha256s",
}
_PRODUCTION_READONLY_ARTIFACT_FIELDS = {
    "schema_version",
    "artifact_kind",
    "status",
    "runtime_profile",
    "env_profile",
    "source_commit",
    "generated_at_utc",
    "capture_count",
    "capture_invocation_ids",
    "capture_query_generations",
    "broker_trading_day",
    "account_fingerprint",
    "env_identity_sha256",
    "formal_framework_realpaths",
    "python_sha256",
    "vnpy_ctp_extension_sha256s",
    "formal_framework_executable_sha256s",
    "query_bundle_complete",
    "account_query_complete",
    "position_query_complete",
    "order_query_complete",
    "trade_query_complete",
    "warm_disconnect_reconnect_fault_tests_passed",
    "natural_disconnect_reconnect_proof_observed",
    "capture_artifacts",
    "send_order_api_called_count",
    "cancel_order_api_called_count",
    "order_api_called_count",
}
_PRODUCTION_READONLY_CAPTURE_FIELDS = {
    "schema_version",
    "artifact_kind",
    "source_commit",
    "generated_at_utc",
    "invocation_id",
    "query_generation",
    "broker_trading_day",
    "account_fingerprint",
    "env_identity_sha256",
    "formal_framework_realpaths",
    "python_sha256",
    "vnpy_ctp_extension_sha256s",
    "formal_framework_executable_sha256s",
    "runtime_profile",
    "env_profile",
    "query_bundle_complete",
    "account_query_complete",
    "position_query_complete",
    "order_query_complete",
    "trade_query_complete",
    "natural_disconnect_reconnect_proof_observed",
    "send_order_api_called_count",
    "cancel_order_api_called_count",
    "order_api_called_count",
    "stage907_summary_artifact",
    "stage174_summary_artifact",
    "stage907_stdout_artifact",
    "query_artifacts",
}
_TRUSTED_RUNNER_FIELDS = {
    "schema_version",
    "artifact_kind",
    "runner_mode",
    "source_commit",
    "tree_fingerprint",
    "python_realpath",
    "python_sha256",
    "vnpy_ctp_extension_sha256s",
    "formal_framework_executable_sha256s",
    "formal_framework_realpaths",
    "cwd_realpath",
    "run_nonce",
    "started_at_utc",
    "finished_at_utc",
    "pytest_environment",
    "readonly_environment",
    "pytest_invocations",
    "readonly_invocations",
}
_TRUSTED_RUNNER_ENVIRONMENT_FIELDS = {
    "schema_version",
    "environment_kind",
    "policy",
    "allowlist_keys",
    "allowlist_sha256",
    "fixed_controls_sha256",
    "environment_sha256",
    "caller_environment_inherited",
    "credential_source",
}
_TRUSTED_PYTEST_INVOCATION_FIELDS = {
    "suite_id",
    "invocation_nonce",
    "argv",
    "python_realpath",
    "python_sha256",
    "vnpy_ctp_extension_sha256s",
    "formal_framework_executable_sha256s",
    "cwd_realpath",
    "started_at_utc",
    "finished_at_utc",
    "returncode",
    "test_file_sha256",
    "junit_artifact_sha256",
    "exit_status_artifact_sha256",
    "output_artifact_path",
    "output_artifact_sha256",
    "environment_sha256",
    "scheduler_policy",
}
_TRUSTED_READONLY_INVOCATION_FIELDS = {
    "capture_index",
    "invocation_nonce",
    "argv",
    "python_realpath",
    "python_sha256",
    "vnpy_ctp_extension_sha256s",
    "formal_framework_executable_sha256s",
    "cwd_realpath",
    "started_at_utc",
    "finished_at_utc",
    "returncode",
    "stage907_summary_sha256",
    "stage174_summary_sha256",
    "stage907_stdout_sha256",
    "account_fingerprint",
    "env_identity_sha256",
    "formal_framework_realpaths",
    "query_artifact_sha256s",
    "environment_sha256",
}
DEFAULT_CRITICAL_FILES = (
    "examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py",
    "examples/portfolio_backtesting/qmt_roll_official_execution_profile.py",
    "examples/portfolio_backtesting/qmt_roll_official_pending_artifact.py",
    "examples/portfolio_backtesting/qmt_roll_official_stage372_shadow_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_candidate_stage777_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_candidate_stage813_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_candidate_stage819_30w_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_candidate_stage847_c9_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_lightweight_context.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_daily_data_receipt.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_email_notify.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_failure_notify.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_postclose_pipeline.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_production_assets.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_launchd_surface.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_c9_intraday_state.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_intent_spool.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_authorization_lock.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_runtime_profile.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_release_manifest.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_submit_authorization.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_journal.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_reader.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_recovery.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_tick_types.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_time.py",
    "examples/portfolio_backtesting/qmt_roll_official_live_trace.py",
    "examples/portfolio_backtesting/audit_qmt_roll_stage179_readonly_canary_qualification.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage179_activation_receipt.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage179_production_qualification_bundle.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage179_rollback_guard.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py",
    "examples/portfolio_backtesting/build_qmt_roll_stage065_top10_fu_formal_ai_bundle.py",
    "examples/portfolio_backtesting/qmt_roll_official_ai_pool_policy.py",
    "examples/portfolio_backtesting/provision_qmt_roll_c9_launchd_directories.py",
    "examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py",
    "examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py",
    "examples/portfolio_backtesting/run_qmt_alignment_backtest.py",
    "examples/portfolio_backtesting/analyze_qmt_roll_stage650_stage526_200k_capital_reality_check.py",
    "examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py",
    "examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
    "examples/portfolio_backtesting/analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
    "examples/portfolio_backtesting/export_qmt_roll_stage372_official_shadow_events.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage907_official_live_readonly_refresh_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage909_official_live_shadow_refresh_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage911_official_live_kill_switch_manager.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage922_official_live_target_date_resolver.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage927_official_live_real_submit_arming_gate.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_owned_child_guard.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage930_supervisor_child.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage934_official_live_automation_health_check.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py",
    "examples/portfolio_backtesting/qmt_roll_strategy_material_manifest.py",
    "examples/portfolio_backtesting/qmt_roll_strategy_material_discovery.py",
    "examples/portfolio_backtesting/build_qmt_roll_official_strategy_material_release.py",
    "examples/portfolio_backtesting/qmt_roll_ai_artifact_registry.py",
    "examples/portfolio_backtesting/qmt_roll_official_strategy_material_resolver.py",
    "examples/portfolio_backtesting/qmt_roll_official_baseline_identity.py",
    "examples/portfolio_backtesting/audit_qmt_roll_official_promotion_closure.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage941_official_live_c9_detector.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage945_official_live_production_session_launcher.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage946_official_live_production_health_check.py",
    "examples/portfolio_backtesting/run_qmt_roll_stage947_official_live_production_support_launcher.py",
    "examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-readonly-day-session.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-readonly-night-session.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-readonly-postclose-precompute.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-day-session.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-night-session.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-day-close-readonly.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-postclose-precompute.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-postclose-report.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-monthly-ai-pool.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-production-live-health.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-direct.plist",
    "examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-supervisor.plist",
    "tests/stage179_performance_gate.py",
    "tests/test_stage179_production_performance_gate.py",
    "tests/test_stage174_query_bundle.py",
    "tests/test_stage179_fault_matrix.py",
    "tests/test_stage179_c9_launchd_directories.py",
    "tests/test_stage179_official_execution_profile.py",
    "tests/test_stage179_performance_gate_diagnostics.py",
    "tests/test_stage179_readonly_canary_qualification.py",
    "tests/test_stage179_release_manifest.py",
    "tests/test_stage907_readonly_refresh_gate.py",
    "tests/test_stage608_continuous_tick_stream.py",
    "tests/test_stage179_stage260_execution_profile.py",
    "tests/test_stage179_stage372_daemon_boundary.py",
    "tests/test_stage179_stage372_daily_intents.py",
    "tests/test_stage179_stage372_submit_boundary.py",
    "tests/test_stage179_stage372_shadow_precompute.py",
    "tests/test_stage179_submit_authorization.py",
    "tests/test_stage179_two_executor_process_race.py",
    "tests/test_stage179_executor_serve.py",
    "tests/test_stage179_activation_receipt_builder.py",
    "tests/test_official_live_config_import.py",
    "tests/test_official_live_execution_ledger_cycles.py",
    "tests/test_official_live_failure_notify.py",
    "tests/test_official_live_postclose_pipeline.py",
    "tests/test_official_live_intent_spool.py",
    "tests/test_official_live_c9_detector.py",
    "tests/test_official_live_c9_intraday_state.py",
    "tests/test_stage905_c9_cycle_intents.py",
    "tests/test_official_live_late_retry_fill.py",
    "tests/test_stage904_durable_state_integration.py",
    "tests/test_stage927_scope_permits.py",
    "tests/test_stage930_fast_lane.py",
    "tests/test_stage930_persistent_authorization.py",
    "tests/test_stage931_authorization_guard.py",
    "tests/test_stage931_ctp_readiness.py",
    "tests/test_stage931_post_reprice_final_gate.py",
    "tests/test_stage931_trade_fill_accounting.py",
    "tests/test_stage934_readonly_health_check.py",
    "tests/test_stage065_top10_fu_formal_ai_bundle.py",
    "tests/test_stage901_official_ai_pool_policy.py",
    "tests/test_stage929_official_ai_pool_policy.py",
    "tests/test_stage935_ai_pool_path_consistency.py",
    "tests/test_strategy_material_manifest.py",
    "tests/test_strategy_material_discovery.py",
    "tests/test_official_strategy_material_release.py",
    "tests/test_ai_artifact_registry.py",
    "tests/test_official_strategy_material_resolver.py",
    "tests/test_official_baseline_identity.py",
    "tests/test_official_promotion_closure.py",
    "tests/test_stage945_production_launcher.py",
    "tests/test_stage946_production_health_check.py",
    "tests/test_stage947_production_support_launcher.py",
    "tests/test_stage948_production_installer.py",
    "tests/test_stage179_production_assets.py",
    "tests/test_stage179_launchd_lifecycle.py",
    "skills/freeze-official-strategy-materials/SKILL.md",
    "skills/freeze-official-strategy-materials/references/material-contract.md",
    "skills/freeze-official-strategy-materials/agents/openai.yaml",
    "skills/version-ab-experiment/SKILL.md",
    "skills/version-ab-experiment/agents/openai.yaml",
    "skills/futures-live-execution-sop/SKILL.md",
    "skills/futures-live-execution-sop/agents/openai.yaml",
    "skills/futures-live-automation-startup/SKILL.md",
    "skills/futures-multicycle-validation/SKILL.md",
    "skills/futures-multicycle-validation/agents/openai.yaml",
    "skills/futures-multicycle-backtest-report/SKILL.md",
)


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_not_canonical:{exc}"
        ) from exc


def production_qualification_evidence_digest(
    payload: Mapping[str, Any],
) -> str:
    core = {
        key: value for key, value in payload.items() if key != "evidence_sha256"
    }
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def serialize_production_qualification_evidence(
    payload: Mapping[str, Any],
) -> bytes:
    try:
        return (
            json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_not_canonical:{exc}"
        ) from exc


def _trusted_runner_environment_sha256(
    environment: Mapping[str, str],
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(
            {str(key): str(value) for key, value in environment.items()}
        )
    ).hexdigest()


def _trusted_runner_environment_allowlist_sha256(
    keys: Iterable[str],
) -> str:
    return hashlib.sha256(
        _canonical_json_bytes(sorted(str(key) for key in keys))
    ).hexdigest()


def _trusted_runner_fixed_controls_sha256(*, readonly: bool) -> str:
    values = dict(_TRUSTED_RUNNER_FIXED_ENVIRONMENT_VALUES)
    if readonly:
        values[TRUSTED_RUNNER_READONLY_GATE_ENV] = "1"
    return _trusted_runner_environment_sha256(values)


def trusted_runner_environment_receipt(
    environment: Mapping[str, str],
    *,
    readonly: bool,
) -> dict[str, Any]:
    """Describe a runner-owned environment without exposing its values."""

    normalized = {
        str(key): str(value) for key, value in environment.items()
    }
    expected_keys = (
        TRUSTED_RUNNER_READONLY_ENVIRONMENT_KEYS
        if readonly
        else TRUSTED_RUNNER_BASE_ENVIRONMENT_KEYS
    )
    if tuple(sorted(normalized)) != expected_keys:
        raise ReleaseManifestError(
            "release_builder_production_runner_environment_keys_invalid"
        )
    if any(
        normalized.get(key) != expected
        for key, expected in _TRUSTED_RUNNER_FIXED_ENVIRONMENT_VALUES.items()
    ):
        raise ReleaseManifestError(
            "release_builder_production_runner_environment_controls_invalid"
        )
    for directory_key in ("HOME", "TMPDIR"):
        value = normalized.get(directory_key, "")
        if not value or not Path(value).is_absolute():
            raise ReleaseManifestError(
                "release_builder_production_runner_environment_path_invalid:"
                f"{directory_key}"
            )
    if readonly:
        if normalized.get(TRUSTED_RUNNER_READONLY_GATE_ENV) != "1":
            raise ReleaseManifestError(
                "release_builder_production_runner_readonly_gate_invalid"
            )
    elif any(
        key.startswith("CTP_") or key.startswith("OFFICIAL_LIVE_")
        for key in normalized
    ):
        raise ReleaseManifestError(
            "release_builder_production_runner_pytest_live_env_present"
        )
    return {
        "schema_version": 1,
        "environment_kind": "production-readonly" if readonly else "pytest",
        "policy": TRUSTED_RUNNER_ENVIRONMENT_POLICY,
        "allowlist_keys": list(expected_keys),
        "allowlist_sha256": _trusted_runner_environment_allowlist_sha256(
            expected_keys
        ),
        "fixed_controls_sha256": _trusted_runner_fixed_controls_sha256(
            readonly=readonly
        ),
        "environment_sha256": _trusted_runner_environment_sha256(normalized),
        "caller_environment_inherited": 0,
        "credential_source": (
            "repo-private-ctp_live.local.env" if readonly else "none"
        ),
    }


def build_trusted_runner_environment(
    *,
    home: Path | str,
    temp_dir: Path | str,
    readonly: bool,
) -> dict[str, str]:
    """Build the complete subprocess environment without caller inheritance."""

    environment = {
        "HOME": str(Path(home).resolve(strict=True)),
        "TMPDIR": str(Path(temp_dir).resolve(strict=True)),
        **_TRUSTED_RUNNER_FIXED_ENVIRONMENT_VALUES,
    }
    if readonly:
        environment[TRUSTED_RUNNER_READONLY_GATE_ENV] = "1"
    trusted_runner_environment_receipt(environment, readonly=readonly)
    return environment


def _validate_trusted_runner_environment_receipt(
    receipt: Any,
    *,
    readonly: bool,
) -> None:
    expected_keys = (
        TRUSTED_RUNNER_READONLY_ENVIRONMENT_KEYS
        if readonly
        else TRUSTED_RUNNER_BASE_ENVIRONMENT_KEYS
    )
    expected = {
        "schema_version": 1,
        "environment_kind": "production-readonly" if readonly else "pytest",
        "policy": TRUSTED_RUNNER_ENVIRONMENT_POLICY,
        "allowlist_keys": list(expected_keys),
        "allowlist_sha256": _trusted_runner_environment_allowlist_sha256(
            expected_keys
        ),
        "fixed_controls_sha256": _trusted_runner_fixed_controls_sha256(
            readonly=readonly
        ),
        "caller_environment_inherited": 0,
        "credential_source": (
            "repo-private-ctp_live.local.env" if readonly else "none"
        ),
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != _TRUSTED_RUNNER_ENVIRONMENT_FIELDS
        or any(receipt.get(key) != value for key, value in expected.items())
        or not isinstance(receipt.get("environment_sha256"), str)
        or not _SHA256_RE.fullmatch(receipt["environment_sha256"])
    ):
        raise ReleaseManifestError(
            "release_builder_production_trusted_runner_environment_invalid:"
            f"{'readonly' if readonly else 'pytest'}"
        )


def _parse_utc_timestamp(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReleaseManifestError(
            f"release_builder_production_evidence_timestamp_invalid:{field_name}"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_timestamp_invalid:{field_name}"
        ) from exc
    if parsed.utcoffset() != timedelta(0):
        raise ReleaseManifestError(
            f"release_builder_production_evidence_timestamp_invalid:{field_name}"
        )
    return parsed


def _validate_evidence_timestamp(
    observed: datetime,
    *,
    manifest_created_at: datetime,
    field_name: str,
) -> None:
    if observed > manifest_created_at + PRODUCTION_QUALIFICATION_MAX_FUTURE_SKEW:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_timestamp_future:{field_name}"
        )
    if manifest_created_at - observed > PRODUCTION_QUALIFICATION_MAX_AGE:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_stale:{field_name}"
        )


def _strict_external_evidence_file(path: Path, *, repo_root: Path) -> bytes:
    candidate = path.expanduser()
    try:
        bundle_metadata = candidate.parent.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            "release_builder_production_evidence_bundle_missing"
        ) from exc
    if (
        stat.S_ISLNK(bundle_metadata.st_mode)
        or not stat.S_ISDIR(bundle_metadata.st_mode)
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_bundle_invalid"
        )
    if bundle_metadata.st_uid != os.getuid():
        raise ReleaseManifestError(
            "release_builder_production_evidence_bundle_owner_mismatch"
        )
    if stat.S_IMODE(bundle_metadata.st_mode) & 0o077:
        raise ReleaseManifestError(
            "release_builder_production_evidence_bundle_permissions_too_open"
        )
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            "release_builder_production_qualification_evidence_required"
        ) from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ReleaseManifestError(
            "release_builder_production_evidence_symlink_forbidden"
        )
    if not stat.S_ISREG(metadata.st_mode):
        raise ReleaseManifestError(
            "release_builder_production_evidence_not_regular_file"
        )
    if metadata.st_uid != os.getuid():
        raise ReleaseManifestError(
            "release_builder_production_evidence_owner_mismatch"
        )
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ReleaseManifestError(
            "release_builder_production_evidence_permissions_too_open"
        )
    resolved = candidate.resolve(strict=True)
    if resolved.is_relative_to(repo_root):
        raise ReleaseManifestError(
            "release_builder_production_evidence_must_be_external"
        )
    try:
        return resolved.read_bytes()
    except OSError as exc:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_read_failed:{exc}"
        ) from exc


def _runtime_file_sha256(path: Path, *, identity: str) -> str:
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            f"release_builder_production_runtime_binary_missing:{identity}"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ReleaseManifestError(
            f"release_builder_production_runtime_binary_invalid:{identity}"
        )
    try:
        return hashlib.sha256(resolved.read_bytes()).hexdigest()
    except OSError as exc:
        raise ReleaseManifestError(
            f"release_builder_production_runtime_binary_unreadable:{identity}"
        ) from exc


def _production_runtime_identity(repo_root: Path) -> dict[str, Any]:
    """Return secret-free identity of the exact production runtime inputs."""

    env_file = repo_root / "examples/portfolio_backtesting/ctp_live.local.env"
    try:
        metadata = env_file.lstat()
    except OSError as exc:
        raise ReleaseManifestError(
            "release_builder_production_env_identity_missing"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ReleaseManifestError(
            "release_builder_production_env_identity_invalid"
        )
    python_path = repo_root / ".py311/bin/python"
    ctp_api_path = (
        repo_root / ".py311/lib/python3.11/site-packages/vnpy_ctp/api"
    )
    formal_framework_path = ctp_api_path / "libs"
    framework_paths = (
        formal_framework_path,
        repo_root / ".py311/lib",
    )
    try:
        python_realpath = str(python_path.resolve(strict=True))
        framework_realpaths = [
            str(path.resolve(strict=True)) for path in framework_paths
        ]
    except OSError as exc:
        raise ReleaseManifestError(
            "release_builder_production_runtime_identity_missing"
        ) from exc
    if len(set(framework_realpaths)) != 2:
        raise ReleaseManifestError(
            "release_builder_production_framework_identity_invalid"
        )
    extension_paths: dict[str, Path] = {}
    for extension_name in ("vnctpmd", "vnctptd"):
        candidates = sorted(ctp_api_path.glob(f"{extension_name}*.so"))
        if len(candidates) != 1:
            raise ReleaseManifestError(
                "release_builder_production_runtime_extension_identity_invalid:"
                f"{extension_name}"
            )
        extension_paths[extension_name] = candidates[0]
    framework_executables = {
        "thostmduserapi_se": (
            formal_framework_path
            / "thostmduserapi_se.framework/Versions/A/thostmduserapi_se"
        ),
        "thosttraderapi_se": (
            formal_framework_path
            / "thosttraderapi_se.framework/Versions/A/thosttraderapi_se"
        ),
    }
    python_sha256 = _runtime_file_sha256(
        Path(python_realpath), identity="python"
    )
    extension_sha256s = {
        name: _runtime_file_sha256(path, identity=f"vnpy_ctp:{name}")
        for name, path in extension_paths.items()
    }
    framework_executable_sha256s = {
        name: _runtime_file_sha256(path, identity=f"framework:{name}")
        for name, path in framework_executables.items()
    }
    env_raw = env_file.read_bytes()
    try:
        env_text = env_raw.decode("utf-8")
        parsed_env: dict[str, str] = {}
        for raw_line in env_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = shlex.split(line, comments=True, posix=True)
            if tokens and tokens[0] == "export":
                tokens = tokens[1:]
            if len(tokens) != 1 or "=" not in tokens[0]:
                continue
            key, value = tokens[0].split("=", 1)
            parsed_env[key] = value
        broker_id = parsed_env.get("CTP_BROKERID", "").strip()
        account_id = parsed_env.get("CTP_USERID", "").strip()
    except (UnicodeDecodeError, ValueError) as exc:
        raise ReleaseManifestError(
            "release_builder_production_env_identity_parse_failed"
        ) from exc
    if not broker_id or not account_id:
        raise ReleaseManifestError(
            "release_builder_production_env_account_identity_missing"
        )
    account_fingerprint = hashlib.sha256(
        f"{broker_id}\0{account_id}".encode("utf-8")
    ).hexdigest()
    return {
        "python_realpath": python_realpath,
        "python_sha256": python_sha256,
        "vnpy_ctp_extension_sha256s": extension_sha256s,
        "formal_framework_executable_sha256s": (
            framework_executable_sha256s
        ),
        "cwd_realpath": str(repo_root.resolve(strict=True)),
        "env_identity_sha256": hashlib.sha256(env_raw).hexdigest(),
        "account_fingerprint": account_fingerprint,
        "formal_framework_realpaths": framework_realpaths,
    }


def _load_verified_bundle_bytes(
    pointer: Mapping[str, Any],
    *,
    bundle_root: Path,
) -> tuple[bytes, str]:
    artifact_path = pointer.get("artifact_path")
    artifact_sha256 = pointer.get("artifact_sha256")
    if (
        not isinstance(artifact_path, str)
        or not artifact_path.strip()
        or not isinstance(artifact_sha256, str)
        or not _SHA256_RE.fullmatch(artifact_sha256)
    ):
        raise ReleaseManifestError(
            "release_builder_production_artifact_pointer_invalid"
        )
    relative = Path(artifact_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ReleaseManifestError(
            "release_builder_production_artifact_path_invalid"
        )
    candidate = bundle_root / relative
    cursor = candidate
    while cursor != bundle_root:
        try:
            metadata = cursor.lstat()
        except OSError as exc:
            raise ReleaseManifestError(
                f"release_builder_production_artifact_missing:{artifact_path}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ReleaseManifestError(
                f"release_builder_production_artifact_symlink_forbidden:{artifact_path}"
            )
        if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ReleaseManifestError(
                f"release_builder_production_artifact_permissions_invalid:{artifact_path}"
            )
        cursor = cursor.parent
    metadata = candidate.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ReleaseManifestError(
            f"release_builder_production_artifact_not_regular:{artifact_path}"
        )
    if metadata.st_uid != os.getuid():
        raise ReleaseManifestError(
            f"release_builder_production_artifact_owner_mismatch:{artifact_path}"
        )
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ReleaseManifestError(
            f"release_builder_production_artifact_permissions_too_open:{artifact_path}"
        )
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(bundle_root):
        raise ReleaseManifestError(
            f"release_builder_production_artifact_outside_bundle:{artifact_path}"
        )
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise ReleaseManifestError(
            f"release_builder_production_artifact_read_failed:{artifact_path}"
        ) from exc
    observed_digest = hashlib.sha256(raw).hexdigest()
    if observed_digest != artifact_sha256:
        raise ReleaseManifestError(
            f"release_builder_production_artifact_digest_mismatch:{artifact_path}"
        )
    return raw, observed_digest


def _load_verified_bundle_artifact(
    pointer: Mapping[str, Any],
    *,
    bundle_root: Path,
) -> tuple[dict[str, Any], str]:
    raw, observed_digest = _load_verified_bundle_bytes(
        pointer,
        bundle_root=bundle_root,
    )
    artifact_path = str(pointer.get("artifact_path", ""))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(
            f"release_builder_production_artifact_json_invalid:{artifact_path}"
        ) from exc
    if not isinstance(payload, dict) or raw != serialize_production_qualification_evidence(
        payload
    ):
        raise ReleaseManifestError(
            f"release_builder_production_artifact_bytes_not_canonical:{artifact_path}"
        )
    return payload, observed_digest


def _load_verified_bundle_raw_json_artifact(
    pointer: Mapping[str, Any],
    *,
    bundle_root: Path,
) -> tuple[dict[str, Any], str]:
    raw, observed_digest = _load_verified_bundle_bytes(
        pointer,
        bundle_root=bundle_root,
    )
    artifact_path = str(pointer.get("artifact_path", ""))
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(
            f"release_builder_production_raw_artifact_json_invalid:{artifact_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReleaseManifestError(
            f"release_builder_production_raw_artifact_json_invalid:{artifact_path}"
        )
    return payload, observed_digest


def _raw_summary_canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _raw_summary_generated_at_utc(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_timestamp_invalid"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_timestamp_invalid"
        )
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def derive_formal_ctp_readonly_capture(
    *,
    stage907_summary: Mapping[str, Any],
    stage174_summary: Mapping[str, Any],
    source_commit: str,
    stage907_summary_artifact: Mapping[str, Any],
    stage174_summary_artifact: Mapping[str, Any],
    stage907_stdout_artifact: Mapping[str, Any],
    query_artifacts: Mapping[str, Mapping[str, Any]],
    env_identity_sha256: str,
    formal_framework_realpaths: Iterable[str],
    python_sha256: str,
    vnpy_ctp_extension_sha256s: Mapping[str, str],
    formal_framework_executable_sha256s: Mapping[str, str],
) -> dict[str, Any]:
    """Derive one qualification capture from the two runtime-owned summaries."""

    if (
        set(stage907_summary_artifact) != _ARTIFACT_POINTER_FIELDS
        or set(stage174_summary_artifact) != _ARTIFACT_POINTER_FIELDS
        or set(stage907_stdout_artifact) != _ARTIFACT_POINTER_FIELDS
    ):
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_pointer_invalid"
        )
    if (
        stage907_summary.get("source_commit") != source_commit
        or stage907_summary.get("stage174_source_commit") != source_commit
        or stage174_summary.get("source_commit") != source_commit
    ):
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_source_mismatch"
        )
    invocation_id = str(stage174_summary.get("invocation_id") or "").strip()
    query_generation = str(
        stage174_summary.get("query_generation_uuid") or ""
    ).strip()
    bundle = stage174_summary.get("broker_query_bundle")
    queries = bundle.get("queries") if isinstance(bundle, Mapping) else None
    artifacts = bundle.get("artifacts") if isinstance(bundle, Mapping) else None
    broker_snapshot = stage174_summary.get("broker_snapshot")
    lifecycle = stage174_summary.get("connection_lifecycle")
    if not isinstance(bundle, Mapping) or not isinstance(queries, Mapping):
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_query_bundle_invalid"
        )
    if not isinstance(artifacts, Mapping):
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_artifacts_invalid"
        )
    broker_day = str(stage174_summary.get("broker_trading_day") or "").strip()
    raw_digest = _raw_summary_canonical_sha256(stage174_summary)
    zero_api_fields = (
        "send_order_api_attempted_count",
        "cancel_order_api_attempted_count",
        "send_order_api_called_count",
        "cancel_order_api_called_count",
        "native_mutation_api_attempted_count",
        "native_mutation_api_called_count",
        "order_api_attempted_count",
        "order_api_called_count",
    )
    command_plan = str(stage907_summary.get("sanitized_command_plan") or "")
    command_runtime_valid = bool(
        "ctp_live.local.env" in command_plan
        and re.search(
            r"vnpy_ctp/api/libs:[^\n]*\.py311/lib",
            command_plan,
        )
        and f"--invocation-id {invocation_id}" in command_plan
    )
    query_complete = {
        name: (
            isinstance(queries.get(name), Mapping)
            and queries[name].get("complete") is True
        )
        for name in ("account", "positions", "orders", "trades", "contracts")
    }
    artifact_bindings_valid = all(
        isinstance(artifacts.get(name), Mapping)
        and artifacts[name].get("row_generation_match") is True
        and artifacts[name].get("row_account_match") is True
        and isinstance(artifacts[name].get("sha256"), str)
        and bool(_SHA256_RE.fullmatch(str(artifacts[name]["sha256"])))
        and type(artifacts[name].get("row_count")) is int
        and int(artifacts[name]["row_count"]) >= 0
        for name in ("orders", "trades", "positions")
    )
    account = bundle.get("account")
    account_fingerprint = str(
        account.get("account_fingerprint", "")
        if isinstance(account, Mapping)
        else ""
    )
    frameworks = [str(item) for item in formal_framework_realpaths]
    extension_sha256s = dict(vnpy_ctp_extension_sha256s)
    framework_executable_sha256s = dict(
        formal_framework_executable_sha256s
    )
    runtime_binary_identity_valid = bool(
        isinstance(python_sha256, str)
        and bool(_SHA256_RE.fullmatch(python_sha256))
        and set(extension_sha256s) == {"vnctpmd", "vnctptd"}
        and set(framework_executable_sha256s)
        == {"thostmduserapi_se", "thosttraderapi_se"}
        and all(
            isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))
            for value in (
                *extension_sha256s.values(),
                *framework_executable_sha256s.values(),
            )
        )
    )
    query_artifact_pointers = {
        str(name): dict(pointer)
        for name, pointer in query_artifacts.items()
    }
    query_artifact_bindings_valid = bool(
        set(query_artifact_pointers) == {"orders", "trades", "positions"}
        and all(
            set(pointer) == _ARTIFACT_POINTER_FIELDS
            and pointer.get("artifact_sha256")
            == (artifacts.get(name) or {}).get("sha256")
            for name, pointer in query_artifact_pointers.items()
        )
    )
    account_valid = bool(
        isinstance(account, Mapping)
        and account.get("login_account_match") is True
        and account.get("response_account_match") is True
        and account.get("trading_account_response_match") is True
        and isinstance(account.get("account_fingerprint"), str)
        and bool(_SHA256_RE.fullmatch(str(account["account_fingerprint"])))
    )
    stage907_valid = bool(
        stage907_summary.get("mode") == "refresh"
        and stage907_summary.get("env_profile") == "production-live"
        and stage907_summary.get("official_live_version")
        == C9_15W_PROFILE.official_version
        and stage907_summary.get("refresh_status")
        == "readonly_refresh_completed_snapshot_ready"
        and stage907_summary.get("refresh_attempted") == 1
        and stage907_summary.get("command_exit_code") == 0
        and stage907_summary.get("blocking_failure_count") == 0
        and stage907_summary.get("readonly_status_after")
        == "readonly_snapshots_received"
        and stage907_summary.get("position_snapshot_state_after")
        in {"confirmed_flat", "positions_received"}
        and stage907_summary.get("order_api_evidence_complete") == 1
        and stage907_summary.get("order_api_evidence_missing_fields") == []
        and stage907_summary.get("order_api_evidence_nonzero_fields") == []
        and stage907_summary.get("snapshot_evidence_complete") == 1
        and stage907_summary.get("snapshot_evidence_missing_fields") == []
        and stage907_summary.get("broker_query_bundle_complete") is True
        and stage907_summary.get("stage174_invocation_id") == invocation_id
        and stage907_summary.get("snapshot_generation_uuid") == query_generation
        and stage907_summary.get("stage174_file_summary_sha256") == raw_digest
        and stage907_summary.get("stage174_stdout_summary_sha256") == raw_digest
        and stage907_summary.get("stage174_stdout_file_payload_match") == 1
        and stage907_summary.get("connection_lifecycle") == lifecycle
        and command_runtime_valid
        and all(
            type(stage907_summary.get(field)) is int
            and int(stage907_summary[field]) == 0
            for field in zero_api_fields
        )
    )
    stage174_valid = bool(
        invocation_id
        and query_generation
        and stage174_summary.get("status") == "readonly_snapshots_received"
        and stage174_summary.get("order_api_called") is False
        and re.fullmatch(r"\d{8}", broker_day)
        and bundle.get("complete") is True
        and bundle.get("generation_uuid") == query_generation
        and bundle.get("broker_trading_day") == broker_day
        and bundle.get("full_snapshot_current_generation") is True
        and bundle.get("trade_order_join_complete") is True
        and bundle.get("trade_identity_complete") is True
        and all(query_complete.values())
        and artifact_bindings_valid
        and query_artifact_bindings_valid
        and account_valid
        and bool(_SHA256_RE.fullmatch(str(env_identity_sha256)))
        and len(frameworks) == 2
        and len(set(frameworks)) == 2
        and all(Path(item).is_absolute() for item in frameworks)
        and runtime_binary_identity_valid
        and isinstance(broker_snapshot, Mapping)
        and broker_snapshot.get("position_snapshot_state")
        in {"confirmed_flat", "positions_received"}
        and isinstance(lifecycle, Mapping)
        and all(
            type(stage174_summary.get(field)) is int
            and int(stage174_summary[field]) == 0
            for field in zero_api_fields
        )
    )
    if not stage907_valid or not stage174_valid:
        raise ReleaseManifestError(
            "release_builder_production_readonly_raw_capture_invalid"
        )
    return {
        "schema_version": 1,
        "artifact_kind": "formal_ctp_readonly_capture",
        "source_commit": source_commit,
        "generated_at_utc": _raw_summary_generated_at_utc(
            stage174_summary.get("generated_at")
        ),
        "invocation_id": invocation_id,
        "query_generation": query_generation,
        "broker_trading_day": broker_day,
        "account_fingerprint": account_fingerprint,
        "env_identity_sha256": env_identity_sha256,
        "formal_framework_realpaths": frameworks,
        "python_sha256": python_sha256,
        "vnpy_ctp_extension_sha256s": extension_sha256s,
        "formal_framework_executable_sha256s": (
            framework_executable_sha256s
        ),
        "runtime_profile": ExecutionRuntimeProfile.PRODUCTION_READONLY.value,
        "env_profile": "ctp_live.local.env",
        "query_bundle_complete": 1,
        "account_query_complete": int(query_complete["account"]),
        "position_query_complete": int(query_complete["positions"]),
        "order_query_complete": int(query_complete["orders"]),
        "trade_query_complete": int(query_complete["trades"]),
        "natural_disconnect_reconnect_proof_observed": int(
            lifecycle.get("proof_complete") == 1
        ),
        "send_order_api_called_count": int(
            stage174_summary["send_order_api_called_count"]
        ),
        "cancel_order_api_called_count": int(
            stage174_summary["cancel_order_api_called_count"]
        ),
        "order_api_called_count": int(stage174_summary["order_api_called_count"]),
        "stage907_summary_artifact": dict(stage907_summary_artifact),
        "stage174_summary_artifact": dict(stage174_summary_artifact),
        "stage907_stdout_artifact": dict(stage907_stdout_artifact),
        "query_artifacts": query_artifact_pointers,
    }


def _junit_counts(raw: bytes, *, suite_id: str) -> dict[str, int]:
    if len(raw) > 64 * 1024 * 1024 or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ReleaseManifestError(
            f"release_builder_production_junit_unsafe:{suite_id}"
        )
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ReleaseManifestError(
            f"release_builder_production_junit_invalid:{suite_id}"
        ) from exc
    test_suites = [
        element
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "testsuite"
    ]
    if not any(str(element.attrib.get("name", "")) == suite_id for element in test_suites):
        raise ReleaseManifestError(
            f"release_builder_production_junit_suite_identity_mismatch:{suite_id}"
        )
    test_cases = [
        element
        for element in root.iter()
        if element.tag.rsplit("}", 1)[-1] == "testcase"
    ]
    failed = 0
    skipped = 0
    errors = 0
    for case in test_cases:
        child_tags = {
            child.tag.rsplit("}", 1)[-1]
            for child in case
        }
        if "error" in child_tags:
            errors += 1
        elif "failure" in child_tags:
            failed += 1
        elif "skipped" in child_tags:
            skipped += 1
    passed = len(test_cases) - failed - errors - skipped
    if passed < 0:
        raise ReleaseManifestError(
            f"release_builder_production_junit_counts_invalid:{suite_id}"
        )
    return {
        "passed_count": passed,
        "failed_count": failed + errors,
        "skipped_count": skipped,
    }


def load_and_validate_production_qualification_evidence(
    path: Path | str,
    *,
    repo_root: Path | str,
    source_commit: str,
    execution_profile: str,
    official_version: str,
    capital: int | float,
    capital_label: str,
    critical_files: Iterable[str | Path],
    manifest_created_at_utc: str,
) -> dict[str, Any]:
    repo = Path(repo_root).expanduser().resolve(strict=True)
    evidence_path = Path(path).expanduser()
    raw = _strict_external_evidence_file(evidence_path, repo_root=repo)
    bundle_root = evidence_path.resolve(strict=True).parent
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ReleaseManifestError(
            f"release_builder_production_evidence_read_failed:{exc}"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != _PRODUCTION_EVIDENCE_FIELDS:
        raise ReleaseManifestError(
            "release_builder_production_evidence_fields_invalid"
        )
    if raw != serialize_production_qualification_evidence(payload):
        raise ReleaseManifestError(
            "release_builder_production_evidence_bytes_not_canonical"
        )
    if payload.get("schema_version") != PRODUCTION_QUALIFICATION_SCHEMA_VERSION:
        raise ReleaseManifestError(
            "release_builder_production_evidence_schema_mismatch"
        )
    if payload.get("evidence_kind") != PRODUCTION_QUALIFICATION_EVIDENCE_KIND:
        raise ReleaseManifestError(
            "release_builder_production_evidence_kind_mismatch"
        )
    digest = payload.get("evidence_sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise ReleaseManifestError(
            "release_builder_production_evidence_digest_invalid"
        )
    if production_qualification_evidence_digest(payload) != digest:
        raise ReleaseManifestError(
            "release_builder_production_evidence_digest_mismatch"
        )
    expected_identity = {
        "source_commit": source_commit,
        "execution_profile": execution_profile,
        "official_version": official_version,
        "capital": capital,
        "capital_label": capital_label,
    }
    for field_name, expected in expected_identity.items():
        if payload.get(field_name) != expected:
            raise ReleaseManifestError(
                f"release_builder_production_evidence_identity_mismatch:{field_name}"
            )
    manifest_created_at = _parse_utc_timestamp(
        manifest_created_at_utc,
        field_name="manifest_created_at_utc",
    )
    evidence_generated_at = _parse_utc_timestamp(
        payload.get("generated_at_utc"),
        field_name="generated_at_utc",
    )
    _validate_evidence_timestamp(
        evidence_generated_at,
        manifest_created_at=manifest_created_at,
        field_name="generated_at_utc",
    )

    expected_rows = release_critical_file_rows(
        repo_root=repo,
        critical_files=critical_files,
    )
    if payload.get("critical_files") != expected_rows:
        raise ReleaseManifestError(
            "release_builder_production_evidence_critical_files_mismatch"
        )
    expected_tree = release_tree_fingerprint(expected_rows)
    if payload.get("tree_fingerprint") != expected_tree:
        raise ReleaseManifestError(
            "release_builder_production_evidence_tree_fingerprint_mismatch"
        )
    critical_hashes = {
        str(row["path"]): str(row["sha256"]) for row in expected_rows
    }

    trusted_runner = payload.get("trusted_runner")
    runtime_identity = _production_runtime_identity(repo)
    if (
        not isinstance(trusted_runner, dict)
        or set(trusted_runner) != _TRUSTED_RUNNER_FIELDS
        or trusted_runner.get("schema_version") != 1
        or trusted_runner.get("artifact_kind")
        != "production_qualification_runner_receipt"
        or trusted_runner.get("runner_mode") != "trusted_subprocess_v1"
        or trusted_runner.get("source_commit") != source_commit
        or trusted_runner.get("tree_fingerprint") != expected_tree
        or trusted_runner.get("python_realpath")
        != runtime_identity["python_realpath"]
        or trusted_runner.get("python_sha256")
        != runtime_identity["python_sha256"]
        or trusted_runner.get("vnpy_ctp_extension_sha256s")
        != runtime_identity["vnpy_ctp_extension_sha256s"]
        or trusted_runner.get("formal_framework_executable_sha256s")
        != runtime_identity["formal_framework_executable_sha256s"]
        or trusted_runner.get("formal_framework_realpaths")
        != runtime_identity["formal_framework_realpaths"]
        or trusted_runner.get("cwd_realpath") != runtime_identity["cwd_realpath"]
        or not isinstance(trusted_runner.get("run_nonce"), str)
        or not re.fullmatch(r"[0-9a-f]{32}", trusted_runner["run_nonce"])
    ):
        raise ReleaseManifestError(
            "release_builder_production_trusted_runner_invalid"
        )
    runner_started_at = _parse_utc_timestamp(
        trusted_runner.get("started_at_utc"),
        field_name="trusted_runner.started_at_utc",
    )
    runner_finished_at = _parse_utc_timestamp(
        trusted_runner.get("finished_at_utc"),
        field_name="trusted_runner.finished_at_utc",
    )
    if (
        runner_started_at > runner_finished_at
        or runner_finished_at > evidence_generated_at
    ):
        raise ReleaseManifestError(
            "release_builder_production_trusted_runner_time_invalid"
        )
    for field_name, observed in (
        ("trusted_runner.started_at_utc", runner_started_at),
        ("trusted_runner.finished_at_utc", runner_finished_at),
    ):
        _validate_evidence_timestamp(
            observed,
            manifest_created_at=manifest_created_at,
            field_name=field_name,
        )
    pytest_environment = trusted_runner.get("pytest_environment")
    readonly_environment = trusted_runner.get("readonly_environment")
    _validate_trusted_runner_environment_receipt(
        pytest_environment,
        readonly=False,
    )
    _validate_trusted_runner_environment_receipt(
        readonly_environment,
        readonly=True,
    )
    pytest_runner_rows = trusted_runner.get("pytest_invocations")
    readonly_runner_rows = trusted_runner.get("readonly_invocations")
    if (
        not isinstance(pytest_runner_rows, list)
        or any(
            not isinstance(row, dict)
            or set(row) != _TRUSTED_PYTEST_INVOCATION_FIELDS
            for row in pytest_runner_rows
        )
        or not isinstance(readonly_runner_rows, list)
        or any(
            not isinstance(row, dict)
            or set(row) != _TRUSTED_READONLY_INVOCATION_FIELDS
            for row in readonly_runner_rows
        )
    ):
        raise ReleaseManifestError(
            "release_builder_production_trusted_runner_invocations_invalid"
        )
    pytest_runner_by_suite = {
        str(row.get("suite_id", "")): row for row in pytest_runner_rows
    }
    if (
        len(pytest_runner_by_suite) != len(pytest_runner_rows)
        or set(pytest_runner_by_suite) != set(PRODUCTION_REQUIRED_TEST_SUITES)
        or len(readonly_runner_rows) < 2
        or [row.get("capture_index") for row in readonly_runner_rows]
        != list(range(len(readonly_runner_rows)))
    ):
        raise ReleaseManifestError(
            "release_builder_production_trusted_runner_coverage_invalid"
        )

    review_pointer = payload.get("review")
    if (
        not isinstance(review_pointer, dict)
        or set(review_pointer) != _ARTIFACT_POINTER_FIELDS
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_pointer_invalid"
        )
    review, _review_digest = _load_verified_bundle_artifact(
        review_pointer,
        bundle_root=bundle_root,
    )
    if set(review) != _PRODUCTION_REVIEW_ARTIFACT_FIELDS:
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_invalid"
        )
    if (
        review.get("schema_version") != 1
        or review.get("artifact_kind") != "independent_production_review"
        or review.get("review_kind") != "independent"
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_not_independent"
        )
    if any(
        not isinstance(review.get(field_name), str)
        or not str(review[field_name]).strip()
        for field_name in ("review_id", "reviewer_identity")
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_identity_missing"
        )
    if review.get("source_commit") != source_commit or review.get(
        "tree_fingerprint"
    ) != expected_tree:
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_source_mismatch"
        )
    report_pointer = {
        "artifact_path": review.get("report_artifact_path"),
        "artifact_sha256": review.get("report_artifact_sha256"),
    }
    report, _report_digest = _load_verified_bundle_artifact(
        report_pointer,
        bundle_root=bundle_root,
    )
    if (
        set(report) != _PRODUCTION_REVIEW_REPORT_FIELDS
        or report.get("schema_version") != 1
        or report.get("artifact_kind")
        != "independent_production_review_report"
        or any(
            report.get(field_name) != review.get(field_name)
            for field_name in (
                "review_id",
                "reviewer_identity",
                "reviewed_at_utc",
                "source_commit",
                "tree_fingerprint",
            )
        )
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_report_mismatch"
        )
    findings = report.get("findings")
    if (
        not isinstance(findings, list)
        or any(
            not isinstance(finding, dict)
            or set(finding) != _PRODUCTION_REVIEW_FINDING_FIELDS
            or not isinstance(finding.get("finding_id"), str)
            or not str(finding.get("finding_id", "")).strip()
            or finding.get("severity") not in {"P0", "P1", "P2"}
            or finding.get("status") not in {"open", "resolved"}
            for finding in findings
        )
        or len({str(finding["finding_id"]) for finding in findings})
        != len(findings)
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_findings_invalid"
        )
    derived_review_counts = {
        f"{severity.lower()}_count": sum(
            1
            for finding in findings
            if finding["severity"] == severity and finding["status"] == "open"
        )
        for severity in ("P0", "P1", "P2")
    }
    if any(
        review.get(field_name) != count
        for field_name, count in derived_review_counts.items()
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_counts_mismatch"
        )
    if review.get("p0_count") != 0 or review.get("p1_count") != 0:
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_blockers_present"
        )
    if type(review.get("p2_count")) is not int or review["p2_count"] < 0:
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_counts_invalid"
        )
    reviewed_at = _parse_utc_timestamp(
        review.get("reviewed_at_utc"),
        field_name="review.reviewed_at_utc",
    )
    _validate_evidence_timestamp(
        reviewed_at,
        manifest_created_at=manifest_created_at,
        field_name="review.reviewed_at_utc",
    )
    if reviewed_at > evidence_generated_at:
        raise ReleaseManifestError(
            "release_builder_production_evidence_review_after_bundle"
        )

    test_pointers = payload.get("required_tests")
    if not isinstance(test_pointers, list) or any(
        not isinstance(item, dict) or set(item) != _TEST_ARTIFACT_POINTER_FIELDS
        for item in test_pointers
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_tests_invalid"
        )
    suite_ids = [str(item.get("suite_id", "")) for item in test_pointers]
    if len(suite_ids) != len(set(suite_ids)) or set(suite_ids) != set(
        PRODUCTION_REQUIRED_TEST_SUITES
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_required_tests_missing"
        )
    test_artifact_digests: dict[str, str] = {}
    test_totals = {"passed_count": 0, "failed_count": 0, "skipped_count": 0}
    for pointer in test_pointers:
        suite_id = str(pointer["suite_id"])
        artifact, artifact_digest = _load_verified_bundle_artifact(
            pointer,
            bundle_root=bundle_root,
        )
        if set(artifact) != _PRODUCTION_TEST_ARTIFACT_FIELDS:
            raise ReleaseManifestError(
                f"release_builder_production_evidence_test_fields_invalid:{suite_id}"
            )
        generated_at = _parse_utc_timestamp(
            artifact.get("generated_at_utc"),
            field_name=f"required_tests.{suite_id}.generated_at_utc",
        )
        _validate_evidence_timestamp(
            generated_at,
            manifest_created_at=manifest_created_at,
            field_name=f"required_tests.{suite_id}.generated_at_utc",
        )
        if generated_at > evidence_generated_at:
            raise ReleaseManifestError(
                f"release_builder_production_evidence_test_after_bundle:{suite_id}"
            )
        junit_raw, _junit_digest = _load_verified_bundle_bytes(
            {
                "artifact_path": artifact.get("junit_artifact_path"),
                "artifact_sha256": artifact.get("junit_artifact_sha256"),
            },
            bundle_root=bundle_root,
        )
        exit_status_raw, _exit_status_digest = _load_verified_bundle_bytes(
            {
                "artifact_path": artifact.get("exit_status_artifact_path"),
                "artifact_sha256": artifact.get("exit_status_artifact_sha256"),
            },
            bundle_root=bundle_root,
        )
        if not re.fullmatch(rb"[0-9]+\n", exit_status_raw):
            raise ReleaseManifestError(
                f"release_builder_production_pytest_exit_status_invalid:{suite_id}"
            )
        exit_code = int(exit_status_raw.decode("ascii").strip())
        derived_counts = _junit_counts(junit_raw, suite_id=suite_id)
        runner_row = pytest_runner_by_suite[suite_id]
        runner_argv = runner_row.get("argv")
        runner_started = _parse_utc_timestamp(
            runner_row.get("started_at_utc"),
            field_name=f"trusted_runner.pytest.{suite_id}.started_at_utc",
        )
        runner_finished = _parse_utc_timestamp(
            runner_row.get("finished_at_utc"),
            field_name=f"trusted_runner.pytest.{suite_id}.finished_at_utc",
        )
        output_pointer = {
            "artifact_path": runner_row.get("output_artifact_path"),
            "artifact_sha256": runner_row.get("output_artifact_sha256"),
        }
        _load_verified_bundle_bytes(output_pointer, bundle_root=bundle_root)
        expected_junit_name = str(artifact.get("junit_artifact_path", ""))
        if suite_id == PRODUCTION_PERFORMANCE_TEST_SUITE:
            expected_argv_prefix = [
                PRODUCTION_PERFORMANCE_TASKPOLICY_PATH,
                "-a",
                runtime_identity["python_realpath"],
                "-m",
                "pytest",
                "-q",
                suite_id,
            ]
            junit_argv_index = 7
            expected_argv_length = 12
            expected_scheduler_policy = (
                PRODUCTION_PERFORMANCE_SCHEDULER_POLICY
            )
        else:
            expected_argv_prefix = [
                runtime_identity["python_realpath"],
                "-m",
                "pytest",
                "-q",
                suite_id,
            ]
            junit_argv_index = 5
            expected_argv_length = 10
            expected_scheduler_policy = PRODUCTION_DIRECT_SCHEDULER_POLICY
        argv_valid = bool(
            isinstance(runner_argv, list)
            and len(runner_argv) == expected_argv_length
            and all(isinstance(value, str) for value in runner_argv)
            and runner_argv[:junit_argv_index] == expected_argv_prefix
            and runner_argv[junit_argv_index].startswith("--junitxml=")
            and Path(
                runner_argv[junit_argv_index].split("=", 1)[1]
            ).name
            == Path(expected_junit_name).name
            and runner_argv[junit_argv_index + 1 :]
            == [
                "-o",
                f"junit_suite_name={suite_id}",
                "-p",
                "no:cacheprovider",
            ]
        )
        if (
            artifact.get("schema_version") != 1
            or artifact.get("artifact_kind") != "pytest_suite_result"
            or artifact.get("suite_id") != suite_id
            or artifact.get("status") != "passed"
            or artifact.get("pytest_exit_code") != exit_code
            or exit_code != 0
            or type(artifact.get("passed_count")) is not int
            or artifact["passed_count"] <= 0
            or artifact.get("failed_count") != 0
            or type(artifact.get("skipped_count")) is not int
            or artifact["skipped_count"] != 0
            or artifact.get("source_commit") != source_commit
            or artifact.get("tree_fingerprint") != expected_tree
            or artifact.get("test_file_sha256") != critical_hashes.get(suite_id)
            or runner_row.get("suite_id") != suite_id
            or runner_row.get("python_realpath")
            != runtime_identity["python_realpath"]
            or runner_row.get("python_sha256")
            != runtime_identity["python_sha256"]
            or runner_row.get("vnpy_ctp_extension_sha256s")
            != runtime_identity["vnpy_ctp_extension_sha256s"]
            or runner_row.get("formal_framework_executable_sha256s")
            != runtime_identity["formal_framework_executable_sha256s"]
            or runner_row.get("cwd_realpath") != runtime_identity["cwd_realpath"]
            or not isinstance(runner_row.get("invocation_nonce"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", runner_row["invocation_nonce"])
            or runner_row.get("returncode") != exit_code
            or runner_row.get("test_file_sha256")
            != critical_hashes.get(suite_id)
            or runner_row.get("junit_artifact_sha256")
            != artifact.get("junit_artifact_sha256")
            or runner_row.get("exit_status_artifact_sha256")
            != artifact.get("exit_status_artifact_sha256")
            or runner_row.get("environment_sha256")
            != pytest_environment.get("environment_sha256")
            or runner_row.get("scheduler_policy")
            != expected_scheduler_policy
            or not argv_valid
            or runner_started < runner_started_at
            or runner_started > runner_finished
            or runner_finished > runner_finished_at
            or any(
                artifact.get(field_name) != count
                for field_name, count in derived_counts.items()
            )
        ):
            raise ReleaseManifestError(
                f"release_builder_production_evidence_test_failed:{suite_id}"
            )
        test_artifact_digests[suite_id] = artifact_digest
        for count_field in test_totals:
            test_totals[count_field] += int(artifact[count_field])

    aggregate_pointer = payload.get("selected_suite_aggregate")
    if (
        not isinstance(aggregate_pointer, dict)
        or set(aggregate_pointer) != _ARTIFACT_POINTER_FIELDS
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_test_aggregate_pointer_invalid"
        )
    aggregate, _aggregate_digest = _load_verified_bundle_artifact(
        aggregate_pointer,
        bundle_root=bundle_root,
    )
    if set(aggregate) != _PRODUCTION_TEST_AGGREGATE_ARTIFACT_FIELDS:
        raise ReleaseManifestError(
            "release_builder_production_evidence_test_aggregate_invalid"
        )
    aggregate_at = _parse_utc_timestamp(
        aggregate.get("generated_at_utc"),
        field_name="selected_suite_aggregate.generated_at_utc",
    )
    _validate_evidence_timestamp(
        aggregate_at,
        manifest_created_at=manifest_created_at,
        field_name="selected_suite_aggregate.generated_at_utc",
    )
    if aggregate_at > evidence_generated_at:
        raise ReleaseManifestError(
            "release_builder_production_evidence_test_aggregate_after_bundle"
        )
    aggregate_exact = {
        "schema_version": 1,
        "artifact_kind": "pytest_selected_suite_aggregate",
        "status": "passed",
        "source_commit": source_commit,
        "tree_fingerprint": expected_tree,
        "suite_ids": sorted(PRODUCTION_REQUIRED_TEST_SUITES),
        **test_totals,
        "result_artifact_sha256s": {
            key: test_artifact_digests[key]
            for key in sorted(test_artifact_digests)
        },
    }
    for field_name, expected in aggregate_exact.items():
        if aggregate.get(field_name) != expected:
            raise ReleaseManifestError(
                f"release_builder_production_evidence_test_aggregate_mismatch:{field_name}"
            )

    readonly_pointer = payload.get("formal_ctp_readonly")
    if (
        not isinstance(readonly_pointer, dict)
        or set(readonly_pointer) != _ARTIFACT_POINTER_FIELDS
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_pointer_invalid"
        )
    readonly, _readonly_digest = _load_verified_bundle_artifact(
        readonly_pointer,
        bundle_root=bundle_root,
    )
    if set(readonly) != _PRODUCTION_READONLY_ARTIFACT_FIELDS:
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_invalid"
        )
    readonly_exact = {
        "schema_version": 1,
        "artifact_kind": "formal_ctp_readonly_qualification",
        "status": "qualified",
        "runtime_profile": ExecutionRuntimeProfile.PRODUCTION_READONLY.value,
        "env_profile": "ctp_live.local.env",
        "source_commit": source_commit,
        "account_fingerprint": runtime_identity["account_fingerprint"],
        "env_identity_sha256": runtime_identity["env_identity_sha256"],
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
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
    }
    if any(readonly.get(key) != value for key, value in readonly_exact.items()):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_incomplete"
        )
    readonly_at = _parse_utc_timestamp(
        readonly.get("generated_at_utc"),
        field_name="formal_ctp_readonly.generated_at_utc",
    )
    _validate_evidence_timestamp(
        readonly_at,
        manifest_created_at=manifest_created_at,
        field_name="formal_ctp_readonly.generated_at_utc",
    )
    if readonly_at > evidence_generated_at:
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_after_bundle"
        )
    capture_pointers = readonly.get("capture_artifacts")
    if (
        not isinstance(capture_pointers, list)
        or len(capture_pointers) < 2
        or any(
            not isinstance(pointer, dict)
            or set(pointer) != _ARTIFACT_POINTER_FIELDS
            for pointer in capture_pointers
        )
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_capture_artifacts_invalid"
        )
    captures: list[dict[str, Any]] = []
    for index, pointer in enumerate(capture_pointers):
        capture, _capture_digest = _load_verified_bundle_artifact(
            pointer,
            bundle_root=bundle_root,
        )
        stage907_pointer = capture.get("stage907_summary_artifact")
        stage174_pointer = capture.get("stage174_summary_artifact")
        stage907_stdout_pointer = capture.get("stage907_stdout_artifact")
        query_artifact_pointers = capture.get("query_artifacts")
        if (
            not isinstance(stage907_pointer, dict)
            or not isinstance(stage174_pointer, dict)
            or set(stage907_pointer) != _ARTIFACT_POINTER_FIELDS
            or set(stage174_pointer) != _ARTIFACT_POINTER_FIELDS
            or not isinstance(stage907_stdout_pointer, dict)
            or set(stage907_stdout_pointer) != _ARTIFACT_POINTER_FIELDS
            or not isinstance(query_artifact_pointers, dict)
            or set(query_artifact_pointers) != {"orders", "trades", "positions"}
            or any(
                not isinstance(raw_pointer, dict)
                or set(raw_pointer) != _ARTIFACT_POINTER_FIELDS
                for raw_pointer in query_artifact_pointers.values()
            )
        ):
            raise ReleaseManifestError(
                f"release_builder_production_evidence_readonly_raw_pointer_invalid:{index}"
            )
        stage907_raw, _stage907_digest = (
            _load_verified_bundle_raw_json_artifact(
                stage907_pointer,
                bundle_root=bundle_root,
            )
        )
        stage174_raw, _stage174_digest = (
            _load_verified_bundle_raw_json_artifact(
                stage174_pointer,
                bundle_root=bundle_root,
            )
        )
        stage907_stdout_raw, stage907_stdout_digest = (
            _load_verified_bundle_bytes(
                stage907_stdout_pointer,
                bundle_root=bundle_root,
            )
        )
        try:
            stage907_stdout_payload = json.loads(
                stage907_stdout_raw.decode("utf-8")
            )
        except Exception as exc:
            raise ReleaseManifestError(
                "release_builder_production_readonly_stdout_invalid:"
                f"{index}"
            ) from exc
        if stage907_stdout_payload != stage907_raw:
            raise ReleaseManifestError(
                "release_builder_production_readonly_stdout_summary_mismatch:"
                f"{index}"
            )
        query_artifact_digests: dict[str, str] = {}
        for name, raw_pointer in query_artifact_pointers.items():
            _raw_query_bytes, raw_query_digest = _load_verified_bundle_bytes(
                raw_pointer,
                bundle_root=bundle_root,
            )
            query_artifact_digests[name] = raw_query_digest
        derived_capture = derive_formal_ctp_readonly_capture(
            stage907_summary=stage907_raw,
            stage174_summary=stage174_raw,
            source_commit=source_commit,
            stage907_summary_artifact=stage907_pointer,
            stage174_summary_artifact=stage174_pointer,
            stage907_stdout_artifact=stage907_stdout_pointer,
            query_artifacts=query_artifact_pointers,
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
        runner_row = readonly_runner_rows[index]
        runner_argv = runner_row.get("argv")
        runner_started = _parse_utc_timestamp(
            runner_row.get("started_at_utc"),
            field_name=f"trusted_runner.readonly.{index}.started_at_utc",
        )
        runner_finished = _parse_utc_timestamp(
            runner_row.get("finished_at_utc"),
            field_name=f"trusted_runner.readonly.{index}.finished_at_utc",
        )
        expected_stage907 = str(
            repo
            / "examples/portfolio_backtesting/"
            "run_qmt_roll_stage907_official_live_readonly_refresh_gate.py"
        )
        readonly_argv_valid = bool(
            isinstance(runner_argv, list)
            and all(isinstance(value, str) for value in runner_argv)
            and runner_argv
            == [
                runtime_identity["python_realpath"],
                expected_stage907,
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
            ]
        )
        if (
            set(capture) != _PRODUCTION_READONLY_CAPTURE_FIELDS
            or capture.get("schema_version") != 1
            or capture.get("artifact_kind") != "formal_ctp_readonly_capture"
            or capture.get("source_commit") != source_commit
            or capture.get("runtime_profile")
            != ExecutionRuntimeProfile.PRODUCTION_READONLY.value
            or capture.get("env_profile") != "ctp_live.local.env"
            or capture.get("env_identity_sha256")
            != runtime_identity["env_identity_sha256"]
            or capture.get("formal_framework_realpaths")
            != runtime_identity["formal_framework_realpaths"]
            or capture.get("python_sha256")
            != runtime_identity["python_sha256"]
            or capture.get("vnpy_ctp_extension_sha256s")
            != runtime_identity["vnpy_ctp_extension_sha256s"]
            or capture.get("formal_framework_executable_sha256s")
            != runtime_identity["formal_framework_executable_sha256s"]
            or any(
                capture.get(field_name) != 1
                for field_name in (
                    "query_bundle_complete",
                    "account_query_complete",
                    "position_query_complete",
                    "order_query_complete",
                    "trade_query_complete",
                )
            )
            or any(
                capture.get(field_name) != 0
                for field_name in (
                    "send_order_api_called_count",
                    "cancel_order_api_called_count",
                    "order_api_called_count",
                )
            )
            or capture.get("natural_disconnect_reconnect_proof_observed")
            not in (0, 1)
            or runner_row.get("capture_index") != index
            or runner_row.get("python_realpath")
            != runtime_identity["python_realpath"]
            or runner_row.get("python_sha256")
            != runtime_identity["python_sha256"]
            or runner_row.get("vnpy_ctp_extension_sha256s")
            != runtime_identity["vnpy_ctp_extension_sha256s"]
            or runner_row.get("formal_framework_executable_sha256s")
            != runtime_identity["formal_framework_executable_sha256s"]
            or runner_row.get("cwd_realpath") != runtime_identity["cwd_realpath"]
            or not isinstance(runner_row.get("invocation_nonce"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", runner_row["invocation_nonce"])
            or runner_row.get("returncode") != 0
            or runner_row.get("stage907_summary_sha256")
            != stage907_pointer.get("artifact_sha256")
            or runner_row.get("stage174_summary_sha256")
            != stage174_pointer.get("artifact_sha256")
            or runner_row.get("stage907_stdout_sha256")
            != stage907_stdout_digest
            or runner_row.get("account_fingerprint")
            != capture.get("account_fingerprint")
            or runner_row.get("env_identity_sha256")
            != runtime_identity["env_identity_sha256"]
            or runner_row.get("formal_framework_realpaths")
            != runtime_identity["formal_framework_realpaths"]
            or runner_row.get("query_artifact_sha256s")
            != query_artifact_digests
            or runner_row.get("environment_sha256")
            != readonly_environment.get("environment_sha256")
            or not readonly_argv_valid
            or runner_started < runner_started_at
            or runner_started > runner_finished
            or runner_finished > runner_finished_at
        ):
            raise ReleaseManifestError(
                f"release_builder_production_evidence_readonly_capture_invalid:{index}"
            )
        if capture != derived_capture:
            raise ReleaseManifestError(
                f"release_builder_production_evidence_readonly_capture_derivation_mismatch:{index}"
            )
        capture_at = _parse_utc_timestamp(
            capture.get("generated_at_utc"),
            field_name=f"formal_ctp_readonly.capture.{index}.generated_at_utc",
        )
        _validate_evidence_timestamp(
            capture_at,
            manifest_created_at=manifest_created_at,
            field_name=f"formal_ctp_readonly.capture.{index}.generated_at_utc",
        )
        if capture_at > readonly_at:
            raise ReleaseManifestError(
                "release_builder_production_evidence_readonly_capture_after_summary"
            )
        captures.append(capture)
    derived_capture_ids = [str(row.get("invocation_id", "")) for row in captures]
    derived_query_generations = [
        str(row.get("query_generation", "")) for row in captures
    ]
    broker_days = {str(row.get("broker_trading_day", "")) for row in captures}
    account_fingerprints = {
        str(row.get("account_fingerprint", "")) for row in captures
    }
    env_identity_hashes = {
        str(row.get("env_identity_sha256", "")) for row in captures
    }
    framework_identities = {
        tuple(str(item) for item in row.get("formal_framework_realpaths", []))
        for row in captures
    }
    python_hashes = {
        str(row.get("python_sha256", "")) for row in captures
    }
    extension_hashes = {
        tuple(sorted(dict(row.get("vnpy_ctp_extension_sha256s", {})).items()))
        for row in captures
    }
    framework_executable_hashes = {
        tuple(
            sorted(
                dict(
                    row.get("formal_framework_executable_sha256s", {})
                ).items()
            )
        )
        for row in captures
    }
    if (
        any(not value.strip() for value in derived_capture_ids)
        or len(set(derived_capture_ids)) != len(derived_capture_ids)
        or any(not value.strip() for value in derived_query_generations)
        or len(set(derived_query_generations)) != len(derived_query_generations)
        or len(broker_days) != 1
        or account_fingerprints != {runtime_identity["account_fingerprint"]}
        or env_identity_hashes != {runtime_identity["env_identity_sha256"]}
        or framework_identities
        != {tuple(runtime_identity["formal_framework_realpaths"])}
        or python_hashes != {runtime_identity["python_sha256"]}
        or extension_hashes
        != {
            tuple(
                sorted(runtime_identity["vnpy_ctp_extension_sha256s"].items())
            )
        }
        or framework_executable_hashes
        != {
            tuple(
                sorted(
                    runtime_identity[
                        "formal_framework_executable_sha256s"
                    ].items()
                )
            )
        }
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_capture_identity_invalid"
        )
    derived_readonly = {
        "capture_count": len(captures),
        "capture_invocation_ids": derived_capture_ids,
        "capture_query_generations": derived_query_generations,
        "broker_trading_day": next(iter(broker_days)),
        "account_fingerprint": next(iter(account_fingerprints)),
        "env_identity_sha256": runtime_identity["env_identity_sha256"],
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
        "natural_disconnect_reconnect_proof_observed": int(
            any(
                row.get("natural_disconnect_reconnect_proof_observed") == 1
                for row in captures
            )
        ),
        "send_order_api_called_count": sum(
            int(row["send_order_api_called_count"]) for row in captures
        ),
        "cancel_order_api_called_count": sum(
            int(row["cancel_order_api_called_count"]) for row in captures
        ),
        "order_api_called_count": sum(
            int(row["order_api_called_count"]) for row in captures
        ),
    }
    if any(
        readonly.get(field_name) != value
        for field_name, value in derived_readonly.items()
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_capture_summary_mismatch"
        )
    if type(readonly.get("capture_count")) is not int or readonly["capture_count"] < 2:
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_capture_incomplete"
        )
    capture_ids = readonly.get("capture_invocation_ids")
    query_generations = readonly.get("capture_query_generations")
    if (
        not isinstance(capture_ids, list)
        or len(capture_ids) < 2
        or any(not isinstance(item, str) or not item.strip() for item in capture_ids)
        or len(capture_ids) != len(set(capture_ids))
        or not isinstance(query_generations, list)
        or len(query_generations) < 2
        or any(
            not isinstance(item, str) or not item.strip()
            for item in query_generations
        )
        or len(query_generations) != len(set(query_generations))
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_capture_identity_invalid"
        )
    broker_trading_day = readonly.get("broker_trading_day")
    if (
        not isinstance(broker_trading_day, str)
        or not re.fullmatch(r"\d{8}", broker_trading_day)
    ):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_trading_day_invalid"
        )
    if readonly.get("natural_disconnect_reconnect_proof_observed") not in (0, 1):
        raise ReleaseManifestError(
            "release_builder_production_evidence_readonly_natural_reconnect_invalid"
        )
    all_nonces = [
        str(row["invocation_nonce"]) for row in pytest_runner_rows
    ] + [str(row["invocation_nonce"]) for row in readonly_runner_rows]
    if len(all_nonces) != len(set(all_nonces)):
        raise ReleaseManifestError(
            "release_builder_production_trusted_runner_nonce_reused"
        )
    return payload


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
    execution_profile: str = ExecutionStrategyMode.C9_15W.value,
    official_version: str | None = None,
    capital: int | float | None = None,
    capital_label: str | None = None,
    critical_files: Iterable[str | Path] = DEFAULT_CRITICAL_FILES,
    allowed_runtime_profiles: Iterable[str | ExecutionRuntimeProfile] = (
        ExecutionRuntimeProfile.OFFLINE,
        ExecutionRuntimeProfile.PRODUCTION_READONLY,
    ),
    created_at_utc: str | None = None,
    strategy_semantics_qualification: dict[str, str] | None = None,
    production_qualification_evidence: Path | str | None = None,
    material_release_id: str | None = None,
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
    if str(execution_profile) == "c9-15w-historical":
        raise ReleaseManifestError(
            "release_builder_deprecated_execution_profile_forbidden"
        )
    profile = resolve_execution_profile(execution_profile)
    assert_profile_identity(
        profile,
        official_version=official_version,
        capital=capital,
        capital_label=capital_label,
    )
    repo = Path(repo_root).expanduser().resolve(strict=True)
    requested_critical_files = tuple(critical_files)
    dirty = _git(repo, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise ReleaseManifestError("release_builder_requires_clean_tree")
    source_commit = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    created = created_at_utc or datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    submit_profiles = {
        ExecutionRuntimeProfile.SIMNOW.value,
        ExecutionRuntimeProfile.BROKER_TEST.value,
        ExecutionRuntimeProfile.PRODUCTION_LIVE.value,
    }
    normalized_runtime_profiles = tuple(
        item.value if isinstance(item, ExecutionRuntimeProfile) else str(item)
        for item in allowed_runtime_profiles
    )
    production_requested = (
        ExecutionRuntimeProfile.PRODUCTION_LIVE.value
        in normalized_runtime_profiles
    )
    material_root = repo / "official_strategy_materials"
    material_files: tuple[str, ...] = ()
    if material_release_id is not None or (material_root / "CURRENT.json").is_file():
        from qmt_roll_official_strategy_material_resolver import (
            ActiveMaterialError,
            active_release_critical_files,
            material_release_critical_files,
        )

        try:
            if material_release_id is not None:
                material_files = material_release_critical_files(
                    material_root,
                    material_release_id,
                )
            else:
                material_files = active_release_critical_files(
                    repo_root=repo,
                    require_deployable=production_requested,
                )
        except ActiveMaterialError as exc:
            raise ReleaseManifestError(
                f"release_builder_material_release_invalid:{exc}"
            ) from exc
    normalized_critical_files = tuple(
        dict.fromkeys((*requested_critical_files, *material_files))
    )
    if production_requested:
        if profile.profile_key != ExecutionStrategyMode.C9_15W.value:
            raise ReleaseManifestError(
                "release_builder_production_live_requires_c9_15w"
            )
        if strategy_semantics_qualification is not None:
            raise ReleaseManifestError(
                "release_builder_production_self_declared_qualification_forbidden"
            )
        if production_qualification_evidence is None:
            raise ReleaseManifestError(
                "release_builder_production_qualification_evidence_required"
            )
        evidence = load_and_validate_production_qualification_evidence(
            production_qualification_evidence,
            repo_root=repo,
            source_commit=source_commit,
            execution_profile=profile.profile_key,
            official_version=official_version,
            capital=capital,
            capital_label=capital_label,
            critical_files=normalized_critical_files,
            manifest_created_at_utc=created,
        )
        qualification = {
            "status": "passed",
            "evidence_id": str(evidence["evidence_sha256"]),
        }
    else:
        if production_qualification_evidence is not None:
            raise ReleaseManifestError(
                "release_builder_production_evidence_without_live_profile"
            )
        qualification = strategy_semantics_qualification or {
            "status": "blocked",
            "evidence_id": "strategy-semantics-evidence-not-provided",
        }
    if (
        execution_profile == ExecutionStrategyMode.STAGE372_20W.value
        and submit_profiles.intersection(normalized_runtime_profiles)
    ):
        raise ReleaseManifestError(
            "release_builder_stage372_semantics_promotion_unsupported"
        )
    if (
        qualification.get("status") != "passed"
        and submit_profiles.intersection(normalized_runtime_profiles)
    ):
        raise ReleaseManifestError(
            "release_builder_strategy_semantics_qualification_required_for_submit"
        )
    payload = build_release_manifest(
        repo_root=repo,
        release_id=release_id,
        execution_profile=execution_profile,
        official_version=official_version,
        capital=capital,
        capital_label=capital_label,
        strategy_semantics_qualification=qualification,
        source_commit=source_commit,
        critical_files=normalized_critical_files,
        allowed_runtime_profiles=normalized_runtime_profiles,
        created_at_utc=created,
        ledger_schema_version=LEDGER_SCHEMA_VERSION,
        intent_fingerprint_versions=(1, INTENT_FINGERPRINT_VERSION_V2),
        reader_capabilities=tuple(sorted(EXECUTION_LEDGER_READER_CAPABILITIES)),
    )
    _assert_manifest_matches_source_commit(repo, source_commit, payload)
    _assert_clean_source_tree(repo, source_commit)
    destination = Path(output_path).expanduser()
    if production_requested:
        destination_parent = destination.parent.resolve(strict=False)
        if destination_parent.is_relative_to(repo):
            raise ReleaseManifestError(
                "release_builder_production_manifest_must_be_external"
            )
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
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.C9_15W.value,
    )
    parser.add_argument("--critical-file", action="append", default=[])
    parser.add_argument("--material-release-id")
    parser.add_argument("--allow-production-live", action="store_true")
    parser.add_argument(
        "--production-qualification-evidence",
        type=Path,
    )
    parser.add_argument("--confirm-production-live-manifest", default="")
    args = parser.parse_args()
    profile = resolve_execution_profile(args.execution_profile)
    if args.allow_production_live:
        if profile.profile_key != ExecutionStrategyMode.C9_15W.value:
            raise ReleaseManifestError(
                "release_builder_production_live_requires_c9_15w"
            )
        if args.production_qualification_evidence is None:
            raise ReleaseManifestError(
                "release_builder_production_qualification_evidence_required"
            )
        if (
            args.confirm_production_live_manifest
            != PRODUCTION_LIVE_MANIFEST_CONFIRM_TEXT
        ):
            raise ReleaseManifestError(
                "release_builder_production_live_confirmation_missing"
            )
        allowed_runtime_profiles = (
            ExecutionRuntimeProfile.OFFLINE,
            ExecutionRuntimeProfile.PRODUCTION_READONLY,
            ExecutionRuntimeProfile.PRODUCTION_LIVE,
        )
        qualification = None
    else:
        allowed_runtime_profiles = (
            ExecutionRuntimeProfile.OFFLINE,
            ExecutionRuntimeProfile.PRODUCTION_READONLY,
        )
        qualification = {
            "status": "blocked",
            "evidence_id": "c9-15w-live-semantics-not-qualified",
        }
    payload = build_release_manifest_file(
        output_path=args.output,
        release_id=args.release_id,
        execution_profile=profile.profile_key,
        official_version=profile.official_version,
        capital=profile.capital,
        capital_label=profile.capital_label,
        critical_files=args.critical_file or DEFAULT_CRITICAL_FILES,
        allowed_runtime_profiles=allowed_runtime_profiles,
        strategy_semantics_qualification=qualification,
        production_qualification_evidence=(
            args.production_qualification_evidence
            if args.allow_production_live
            else None
        ),
        material_release_id=args.material_release_id,
    )
    print(payload["manifest_sha256"])


if __name__ == "__main__":
    main()
