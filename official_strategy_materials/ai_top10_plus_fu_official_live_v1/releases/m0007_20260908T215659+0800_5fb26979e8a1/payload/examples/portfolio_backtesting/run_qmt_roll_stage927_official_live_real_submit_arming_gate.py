from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_FAMILY_VERSION,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    CONTROLLER_HEARTBEAT_PATH,
    KILL_SWITCH_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ENABLED_ENV,
    build_phase_d_config,
)
from run_qmt_roll_stage945_official_live_production_session_launcher import (
    ProductionSessionLaunchError,
    _validate_code_qualification,
    _validate_release_and_receipt,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage927_official_live_real_submit_arming_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage927_official_live_real_submit_arming_gate"
CURRENT_C9_FAMILY_VERSION = "stage819_c9_intraday_stop_retry"
SCOPE_CAPABILITY_SCHEMA_VERSION = 2
_SHA256_HEX_LENGTH = 64

_SCOPE_COMMON_REQUIRED_CHECKS = (
    "profile_is_current_c9",
    "acceptance_suite_passed_fail_closed",
    "completion_audit_proven",
    "controller_not_killed_and_no_order_api",
    "health_alive",
    "static_order_boundary_passed",
    "scheduler_dynamic_target_ready",
    "no_unresolved_fail_closed_incident",
    "account_recovery_not_required",
    "account_recovery_ack_suite_passed",
    "aligned_idle_integration_passed",
    "kill_switch_inactive",
    "scope_evidence_current_official_identity",
    "scope_controller_capability_baseline",
    "scope_broker_account_snapshot_usable",
    "scope_order_api_evidence_complete_zero",
    "scope_real_submit_env_enabled",
    "scope_real_submit_confirm_exact",
)
_SCOPE_REQUIRED_CHECKS = {
    "reduce_close": _SCOPE_COMMON_REQUIRED_CHECKS,
    "retry_open": (
        *_SCOPE_COMMON_REQUIRED_CHECKS,
        "broker_shadow_reconcile_aligned",
    ),
    "initial_open": (
        *_SCOPE_COMMON_REQUIRED_CHECKS,
        "broker_shadow_reconcile_aligned",
    ),
}
_SCOPE_EXCLUDED_TRANSIENT_CHECKS = {
    "reduce_close": (
        "controller_live_real_clean_ready",
        "broker_shadow_reconcile_aligned",
    ),
    "retry_open": ("controller_live_real_clean_ready",),
    "initial_open": ("controller_live_real_clean_ready",),
}


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = _date_key(target_date)
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _latest(pattern: str) -> Path | None:
    rows = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _target_summary(prefix: str, target_date: str, model_tag: str) -> Path | None:
    path = OUTPUT_DIR / f"{prefix}_summary_{_date_key(target_date)}_{model_tag}.json"
    return path if path.exists() else None


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _age_seconds(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        generated_at = datetime.fromisoformat(text)
    except ValueError:
        return None
    now = datetime.now(tz=generated_at.tzinfo) if generated_at.tzinfo else datetime.now()
    return round((now - generated_at).total_seconds(), 3)


def _load_production_authority(
    *,
    release_manifest: Path,
    activation_receipt: Path,
    qualification_evidence: Path,
    runtime_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    raw_payloads = {
        "release_manifest": _read_json(release_manifest),
        "activation_receipt": _read_json(activation_receipt),
        "production_qualification": _read_json(qualification_evidence),
    }
    try:
        manifest = _validate_release_and_receipt(
            release_manifest=release_manifest,
            activation_receipt=activation_receipt,
            runtime_root=runtime_root,
        )
        qualification = _validate_code_qualification(
            manifest=manifest,
            qualification_evidence=qualification_evidence,
        )
    except (ProductionSessionLaunchError, OSError, ValueError) as exc:
        return (
            {
                "authority_status": "production_authority_blocked_fail_closed",
                "blocker": f"{type(exc).__name__}:{exc}",
                "order_api_called_count": None,
            },
            raw_payloads,
        )
    return (
        {
            "authority_status": "production_authority_validated",
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "execution_profile": C9_15W_PROFILE.profile_key,
            "capital": OFFICIAL_LIVE_CAPITAL,
            "capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
            "source_commit": manifest.get("source_commit"),
            "tree_fingerprint": manifest.get("tree_fingerprint"),
            "manifest_sha256": manifest.get("manifest_sha256"),
            "qualification_evidence_sha256": qualification.get("evidence_sha256"),
            "order_api_called_count": 0,
        },
        raw_payloads,
    )


def _to_int(value: Any, default: int = -1) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _to_float(value: Any, default: float = -1.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _env_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _active(payload: dict[str, Any]) -> bool:
    return bool(payload.get("enabled", False) or payload.get("kill_switch_active", False))


def _canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == _SHA256_HEX_LENGTH and all(
        character in "0123456789abcdef" for character in text
    )


def _flag_one(value: Any) -> bool:
    return (type(value) is int and value == 1) or value is True


def _strict_zero(value: Any) -> bool:
    return type(value) is int and value == 0


def _strict_source_order_api_zero(
    payloads: dict[str, dict[str, Any]],
    *,
    account_recovery_not_required: bool,
) -> tuple[bool, dict[str, Any]]:
    required_sources = [
        "stage903",
        "stage906",
        "controller_heartbeat",
        "production_authority",
        "stage923",
        "stage924",
    ]
    if not account_recovery_not_required:
        required_sources.append("stage925")
    observed = {
        name: payloads.get(name, {}).get("order_api_called_count")
        for name in required_sources
    }
    return all(_strict_zero(value) for value in observed.values()), observed


def _scope_identity_observed(
    payloads: dict[str, dict[str, Any]],
    *,
    target_date: str,
    account_recovery_not_required: bool,
) -> tuple[bool, dict[str, Any]]:
    identity_sources = [
        "stage903",
        "stage906",
        "production_authority",
        "stage923",
        "stage924",
    ]
    if not account_recovery_not_required:
        identity_sources.append("stage925")
    dated_sources = {"stage903", "stage906", "stage923", "stage924", "stage925"}
    observed: dict[str, Any] = {}
    passed = True
    for name in identity_sources:
        payload = payloads.get(name, {})
        row = {
            "official_live_version": payload.get("official_live_version"),
            "official_live_alias": payload.get("official_live_alias"),
        }
        row_passed = bool(payload)
        row_passed = (
            row_passed
            and payload.get("official_live_version") == OFFICIAL_LIVE_VERSION
        )
        row_passed = (
            row_passed and payload.get("official_live_alias") == OFFICIAL_LIVE_ALIAS
        )
        if name in dated_sources:
            row["target_date"] = payload.get("target_date")
            row_passed = row_passed and payload.get("target_date") == target_date
        observed[name] = row
        passed = passed and row_passed

    controller = payloads.get("stage903", {})
    observed["execution_identity"] = {
        "execution_profile": controller.get("execution_profile"),
        "capital": controller.get("capital"),
        "capital_label": controller.get("capital_label"),
    }
    passed = passed and controller.get("execution_profile") == C9_15W_PROFILE.profile_key
    passed = passed and type(controller.get("capital")) in (int, float)
    passed = passed and not isinstance(controller.get("capital"), bool)
    passed = passed and float(controller.get("capital", -1)) == OFFICIAL_LIVE_CAPITAL
    passed = passed and controller.get("capital_label") == OFFICIAL_LIVE_CAPITAL_LABEL
    return bool(passed), observed


def _controller_scope_baseline(
    stage903: dict[str, Any],
    *,
    target_date: str,
) -> tuple[bool, dict[str, Any]]:
    executor_status = stage903.get("stage905_executor_status")
    ready_count = stage903.get("stage905_ready_count")
    blocked_count = stage903.get("stage905_blocked_count")
    ready_state_valid = (
        executor_status == "executor_dry_run_ready"
        and type(ready_count) is int
        and ready_count > 0
    )
    idle_state_valid = (
        executor_status == "executor_no_intents"
        and _strict_zero(ready_count)
    )
    controller_state_valid = (
        ready_state_valid
        and stage903.get("controller_status")
        == "phase_d_controller_live_real_ready_no_submit_step"
    ) or (
        idle_state_valid
        and stage903.get("controller_status")
        == "phase_d_controller_live_real_blocked"
    )
    observed = {
        "target_date": stage903.get("target_date"),
        "mode": stage903.get("mode"),
        "controller_status": stage903.get("controller_status"),
        "kill_switch_active": stage903.get("kill_switch_active"),
        "execution_profile": stage903.get("execution_profile"),
        "capital": stage903.get("capital"),
        "capital_label": stage903.get("capital_label"),
        "order_api_called_count": stage903.get("order_api_called_count"),
        "send_order_api_called_count": stage903.get("send_order_api_called_count"),
        "cancel_order_api_called_count": stage903.get("cancel_order_api_called_count"),
        "order_api_evidence_complete": stage903.get("order_api_evidence_complete"),
        "stage905_exit_code": stage903.get("stage905_exit_code"),
        "stage905_executor_status": executor_status,
        "stage905_ready_count": ready_count,
        "stage905_blocked_count": blocked_count,
        "stage914_exit_code": stage903.get("stage914_exit_code"),
        "stage914_preflight_status": stage903.get("stage914_preflight_status"),
        "stage914_blocking_failure_count": stage903.get("stage914_blocking_failure_count"),
        "stage914_order_api_called_count": stage903.get("stage914_order_api_called_count"),
    }
    passed = (
        bool(stage903)
        and stage903.get("target_date") == target_date
        and stage903.get("mode") == "live-real"
        and stage903.get("official_live_version") == OFFICIAL_LIVE_VERSION
        and stage903.get("official_live_alias") == OFFICIAL_LIVE_ALIAS
        and stage903.get("execution_profile") == C9_15W_PROFILE.profile_key
        and type(stage903.get("capital")) in (int, float)
        and not isinstance(stage903.get("capital"), bool)
        and float(stage903.get("capital", -1)) == OFFICIAL_LIVE_CAPITAL
        and stage903.get("capital_label") == OFFICIAL_LIVE_CAPITAL_LABEL
        and stage903.get("kill_switch_active") is False
        and _strict_zero(stage903.get("order_api_called_count"))
        and _strict_zero(stage903.get("send_order_api_called_count"))
        and _strict_zero(stage903.get("cancel_order_api_called_count"))
        and _flag_one(stage903.get("order_api_evidence_complete"))
        and _strict_zero(stage903.get("stage905_exit_code"))
        and _strict_zero(blocked_count)
        and controller_state_valid
        and _strict_zero(stage903.get("stage914_exit_code"))
        and stage903.get("stage914_preflight_status")
        == "production_readonly_preflight_passed"
        and _strict_zero(stage903.get("stage914_blocking_failure_count"))
        and _strict_zero(stage903.get("stage914_order_api_called_count"))
    )
    return bool(passed), observed


def _broker_scope_baseline(
    stage903: dict[str, Any],
    stage906: dict[str, Any],
    *,
    target_date: str,
) -> tuple[bool, dict[str, Any]]:
    snapshot_age = _to_float(stage906.get("readonly_snapshot_age_seconds"), -1.0)
    max_snapshot_age = _to_float(
        stage906.get(
            "max_snapshot_age_seconds",
            (stage906.get("phase_d_hard_limits") or {}).get("max_snapshot_age_seconds")
            if isinstance(stage906.get("phase_d_hard_limits"), dict)
            else None,
        ),
        -1.0,
    )
    stage907_hashes = (
        stage903.get("stage907_stage174_file_summary_sha256"),
        stage903.get("stage907_stage174_stdout_summary_sha256"),
    )
    observed = {
        "stage906": {
            "target_date": stage906.get("target_date"),
            "official_live_version": stage906.get("official_live_version"),
            "broker_snapshot_ready": stage906.get("broker_snapshot_ready"),
            "readonly_status": stage906.get("readonly_status"),
            "readonly_snapshot_age_seconds": stage906.get(
                "readonly_snapshot_age_seconds"
            ),
            "max_snapshot_age_seconds": max_snapshot_age,
            "position_snapshot_state": stage906.get("position_snapshot_state"),
            "active_broker_order_count": stage906.get("active_broker_order_count"),
            "order_api_called_count": stage906.get("order_api_called_count"),
        },
        "stage907_via_controller": {
            "env_profile": stage903.get("stage907_env_profile"),
            "refresh_status": stage903.get("stage907_refresh_status"),
            "readonly_status_after": stage903.get("stage907_readonly_status_after"),
            "position_snapshot_state_after": stage903.get(
                "stage907_position_snapshot_state_after"
            ),
            "snapshot_evidence_complete": stage903.get(
                "stage907_snapshot_evidence_complete"
            ),
            "broker_query_bundle_complete": stage903.get(
                "stage907_broker_query_bundle_complete"
            ),
            "stdout_file_payload_match": stage903.get(
                "stage907_stage174_stdout_file_payload_match"
            ),
            "snapshot_generation_uuid": stage903.get("stage907_snapshot_generation_uuid"),
            "stage174_invocation_id": stage903.get("stage907_stage174_invocation_id"),
            "file_summary_sha256": stage907_hashes[0],
            "stdout_summary_sha256": stage907_hashes[1],
        },
    }
    passed = (
        bool(stage906)
        and stage906.get("target_date") == target_date
        and stage906.get("official_live_version") == OFFICIAL_LIVE_VERSION
        and _flag_one(stage906.get("broker_snapshot_ready"))
        and stage906.get("readonly_status") == "readonly_snapshots_received"
        and snapshot_age >= 0
        and max_snapshot_age > 0
        and snapshot_age <= max_snapshot_age
        and stage906.get("position_snapshot_state")
        in {"confirmed_flat", "positions_received"}
        and _strict_zero(stage906.get("active_broker_order_count"))
        and _strict_zero(stage906.get("order_api_called_count"))
        and stage903.get("stage907_env_profile") == "production-live"
        and stage903.get("stage907_refresh_status")
        == "readonly_refresh_completed_snapshot_ready"
        and stage903.get("stage907_readonly_status_after") == "readonly_snapshots_received"
        and stage903.get("stage907_position_snapshot_state_after")
        in {"confirmed_flat", "positions_received"}
        and _flag_one(stage903.get("stage907_snapshot_evidence_complete"))
        and _flag_one(stage903.get("stage907_broker_query_bundle_complete"))
        and _flag_one(stage903.get("stage907_stage174_stdout_file_payload_match"))
        and bool(str(stage903.get("stage907_snapshot_generation_uuid") or "").strip())
        and bool(str(stage903.get("stage907_stage174_invocation_id") or "").strip())
        and all(_is_sha256(value) for value in stage907_hashes)
        and stage907_hashes[0] == stage907_hashes[1]
    )
    return bool(passed), observed


def _check(
    rows: list[dict[str, Any]],
    *,
    check: str,
    category: str,
    passed: bool,
    severity: str,
    observed: Any,
    required: Any,
    blocker: str,
) -> None:
    rows.append(
        {
            "check": check,
            "category": category,
            "passed": int(bool(passed)),
            "severity": severity,
            "observed": observed,
            "required": required,
            "blocker": "" if passed else blocker,
        }
    )


def _append_scope_capability_checks(
    rows: list[dict[str, Any]],
    *,
    payloads: dict[str, dict[str, Any]],
    target_date: str,
    account_recovery_not_required: bool,
    real_submit_env_enabled: bool,
    confirm_live_real_ok: bool,
) -> None:
    identity_passed, identity_observed = _scope_identity_observed(
        payloads,
        target_date=target_date,
        account_recovery_not_required=account_recovery_not_required,
    )
    _check(
        rows,
        check="scope_evidence_current_official_identity",
        category="scope_capability",
        passed=identity_passed,
        severity="scope_block",
        observed=identity_observed,
        required=(
            f"all required evidence uses {OFFICIAL_LIVE_VERSION}/{OFFICIAL_LIVE_ALIAS}; "
            f"execution_profile={C9_15W_PROFILE.profile_key};capital={OFFICIAL_LIVE_CAPITAL:g};"
            f"capital_label={OFFICIAL_LIVE_CAPITAL_LABEL};dated evidence matches {target_date}"
        ),
        blocker="scope_evidence_official_identity_mismatch",
    )

    controller_passed, controller_observed = _controller_scope_baseline(
        payloads.get("stage903", {}),
        target_date=target_date,
    )
    _check(
        rows,
        check="scope_controller_capability_baseline",
        category="scope_capability",
        passed=controller_passed,
        severity="scope_block",
        observed=controller_observed,
        required=(
            "current C9/15w live-real controller + production runtime preflight + complete zero order-API "
            "evidence + Stage905 either exact ready or exact no-intents idle with blocked=0"
        ),
        blocker="scope_controller_capability_baseline_not_proven",
    )

    broker_passed, broker_observed = _broker_scope_baseline(
        payloads.get("stage903", {}),
        payloads.get("stage906", {}),
        target_date=target_date,
    )
    _check(
        rows,
        check="scope_broker_account_snapshot_usable",
        category="scope_capability",
        passed=broker_passed,
        severity="scope_block",
        observed=broker_observed,
        required=(
            "fresh production-live account/position query bundle with matched immutable readback digests, "
            "usable position state, no active broker order, and order_api=0"
        ),
        blocker="scope_broker_account_snapshot_not_usable",
    )

    order_api_passed, order_api_observed = _strict_source_order_api_zero(
        payloads,
        account_recovery_not_required=account_recovery_not_required,
    )
    _check(
        rows,
        check="scope_order_api_evidence_complete_zero",
        category="scope_capability",
        passed=order_api_passed,
        severity="scope_block",
        observed=order_api_observed,
        required="every required source has an explicit integer order_api_called_count=0",
        blocker="scope_order_api_evidence_missing_or_nonzero",
    )
    _check(
        rows,
        check="scope_real_submit_env_enabled",
        category="scope_capability",
        passed=real_submit_env_enabled,
        severity="scope_block",
        observed=real_submit_env_enabled,
        required=f"{PHASE_D_REAL_ENABLED_ENV}=1",
        blocker="scope_real_submit_env_not_enabled",
    )
    _check(
        rows,
        check="scope_real_submit_confirm_exact",
        category="scope_capability",
        passed=confirm_live_real_ok,
        severity="scope_block",
        observed=confirm_live_real_ok,
        required="exact production-live confirmation text",
        blocker="scope_real_submit_confirm_missing_or_wrong",
    )


def _check_evidence(checks: pd.DataFrame) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    if checks.empty:
        return evidence
    for row in checks.to_dict(orient="records"):
        name = str(row.get("check", ""))
        if not name:
            continue
        if name in evidence:
            raise ValueError(f"stage927_duplicate_check_name:{name}")
        evidence[name] = {
            "passed": _to_int(row.get("passed"), 0),
            "severity": str(row.get("severity", "")),
            "observed": row.get("observed"),
            "required": row.get("required"),
            "blocker": str(row.get("blocker", "")),
        }
    return evidence


def _build_scope_capabilities(
    *,
    checks: pd.DataFrame,
    payloads: dict[str, dict[str, Any]],
    source_paths: dict[str, Path | None],
    target_date: str,
    real_submit_env_enabled: bool,
    confirm_live_real_ok: bool,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    check_evidence = _check_evidence(checks)
    capabilities: dict[str, Any] = {}
    permit_fields = {
        "reduce_close": "reduce_close_submit_permitted",
        "retry_open": "retry_open_submit_permitted",
        "initial_open": "initial_open_submit_permitted",
    }
    for scope_name, required_checks in _SCOPE_REQUIRED_CHECKS.items():
        failed_checks = [
            check_name
            for check_name in required_checks
            if check_evidence.get(check_name, {}).get("passed") != 1
        ]
        capabilities[scope_name] = {
            "permit_field": permit_fields[scope_name],
            "permitted": int(not failed_checks),
            "required_checks": list(required_checks),
            "failed_checks": failed_checks,
            "excluded_transient_checks": list(
                _SCOPE_EXCLUDED_TRANSIENT_CHECKS[scope_name]
            ),
            "requires_fresh_downstream_gates": [
                "Stage902 scope-specific readiness",
                "exact durable spool candidate snapshot",
                "fresh broker generation/account/position gate",
                "final tick/price/order boundary gate",
            ],
        }

    source_evidence = {
        name: {
            "path": str(path.resolve()) if path else "",
            "payload_sha256": _canonical_json_sha256(payloads.get(name, {})),
        }
        for name, path in sorted(source_paths.items())
    }
    relevant_check_names = sorted(
        set(_SCOPE_COMMON_REQUIRED_CHECKS)
        | {"broker_shadow_reconcile_aligned"}
    )
    scope_inputs = {
        "schema_version": SCOPE_CAPABILITY_SCHEMA_VERSION,
        "model_tag": MODEL_TAG,
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "execution_profile": C9_15W_PROFILE.profile_key,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
        "env_real_submit_enabled": int(real_submit_env_enabled),
        "confirm_live_real_ok": int(confirm_live_real_ok),
        "check_evidence": {
            name: check_evidence.get(
                name,
                {
                    "passed": 0,
                    "severity": "missing",
                    "observed": None,
                    "required": None,
                    "blocker": "scope_required_check_missing",
                },
            )
            for name in relevant_check_names
        },
        "source_evidence": source_evidence,
    }
    scope_evidence_digest = _canonical_json_sha256(
        {
            "scope_evidence_inputs": scope_inputs,
            "scope_capabilities": capabilities,
        }
    )
    return scope_inputs, capabilities, scope_evidence_digest


def verify_scope_evidence_digest(
    *,
    scope_evidence_inputs: dict[str, Any],
    scope_capabilities: dict[str, Any],
    scope_evidence_digest: str,
) -> bool:
    """Verify the exact Stage927 capability inputs and decisions as one unit."""

    expected = _canonical_json_sha256(
        {
            "scope_evidence_inputs": scope_evidence_inputs,
            "scope_capabilities": scope_capabilities,
        }
    )
    normalized = str(scope_evidence_digest).strip().lower()
    return _is_sha256(normalized) and hmac.compare_digest(expected, normalized)


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    failed = checks[checks["passed"].eq(0)] if not checks.empty else pd.DataFrame()
    return "\n".join(
        [
            "# Stage927 Official Live Real-Submit Arming Gate",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Execution identity: `{summary['execution_profile']}` / `{summary['capital']:g}` / `{summary['capital_label']}`",
            f"- Target date: `{summary['target_date']}`",
            f"- Arming status: `{summary['arming_status']}`",
            f"- Real submit permitted: `{summary['real_submit_permitted']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Reduce-close capability: `{summary['reduce_close_submit_permitted']}`",
            f"- Retry-open capability: `{summary['retry_open_submit_permitted']}`",
            f"- Initial-open capability: `{summary['initial_open_submit_permitted']}`",
            f"- Scope evidence digest: `{summary['scope_evidence_digest']}`",
            f"- Blockers: `{summary['blocking_failure_count']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Scope Capabilities",
            "",
            _to_markdown(
                pd.DataFrame(
                    [
                        {
                            "scope": name,
                            "permitted": payload.get("permitted", 0),
                            "failed_checks": ",".join(payload.get("failed_checks", [])),
                            "excluded_transient_checks": ",".join(
                                payload.get("excluded_transient_checks", [])
                            ),
                        }
                        for name, payload in summary.get("scope_capabilities", {}).items()
                    ]
                ),
                ["scope", "permitted", "failed_checks", "excluded_transient_checks"],
            ),
            "",
            "## Failed Checks",
            "",
            _to_markdown(failed, ["check", "category", "severity", "observed", "required", "blocker"]),
            "",
            "## All Checks",
            "",
            _to_markdown(checks, ["check", "category", "passed", "severity", "observed", "required"]),
            "",
            "## Notes",
            "",
            "- Stage927 is a read-only arming gate. It does not connect CTP, refresh data, submit, or cancel orders.",
            "- Static and one-time engineering evidence comes from the source-commit-bound production qualification and activation chain; dynamic controller, reconciliation, incident, recovery, heartbeat, broker, tick, and order evidence remains mandatory per cycle.",
            "- Even with all evidence green, live submit still requires the real-submit env switch and the exact confirmation text.",
            "- Scope capability is not an order authorization. Stage902, the exact durable spool candidate, broker generation/account/position, and the final tick/price boundary must all be revalidated downstream.",
            "- Reduce-close capability may ignore only current ready-intent absence and a transient shadow reconciliation mismatch; it still requires a complete production-live broker account/position query bundle.",
            "- Retry-open and initial-open are new-risk capabilities: both continue to require shadow/broker reconciliation alignment, while current Stage905 ready-intent presence is delegated to the exact downstream spool admission gate.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D real-submit arming gate.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument("--release-manifest", default="")
    parser.add_argument("--activation-receipt", default="")
    parser.add_argument("--production-qualification-evidence", default="")
    parser.add_argument("--stage179-runtime-root", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)

    source_paths: dict[str, Path | None] = {
        "stage903": _latest("qmt_roll_stage903_official_live_phase_d_controller_summary_*_stage903_official_live_phase_d_controller_v1.json"),
        "controller_heartbeat": CONTROLLER_HEARTBEAT_PATH,
        "stage906": _target_summary(
            "qmt_roll_stage906_official_live_reconciliation_worker",
            args.target_date,
            "stage906_official_live_reconciliation_worker_v1",
        ),
        "stage923": _target_summary(
            "qmt_roll_stage923_official_live_fail_closed_incident",
            args.target_date,
            "stage923_official_live_fail_closed_incident_v1",
        ),
        "stage924": _target_summary(
            "qmt_roll_stage924_official_live_account_recovery_gate",
            args.target_date,
            "stage924_official_live_account_recovery_gate_v1",
        ),
        "stage925": _target_summary(
            "qmt_roll_stage925_official_live_account_recovery_ack_suite",
            args.target_date,
            "stage925_official_live_account_recovery_ack_suite_v1",
        ),
        "stage932": _latest("qmt_roll_stage932_official_live_ctp_smoke_order_summary_*_stage932_official_live_ctp_smoke_order_v1.json"),
        "kill_switch": KILL_SWITCH_PATH if KILL_SWITCH_PATH.exists() else None,
        "release_manifest": Path(args.release_manifest) if args.release_manifest else None,
        "activation_receipt": Path(args.activation_receipt) if args.activation_receipt else None,
        "production_qualification": (
            Path(args.production_qualification_evidence)
            if args.production_qualification_evidence
            else None
        ),
    }
    payloads = {name: _read_json(path) for name, path in source_paths.items()}

    authority, authority_payloads = _load_production_authority(
        release_manifest=Path(args.release_manifest or "__missing_release_manifest__"),
        activation_receipt=Path(args.activation_receipt or "__missing_activation_receipt__"),
        qualification_evidence=Path(
            args.production_qualification_evidence
            or "__missing_production_qualification__"
        ),
        runtime_root=Path(args.stage179_runtime_root or "__missing_runtime_root__"),
    )
    payloads.update(authority_payloads)
    payloads["production_authority"] = authority
    source_paths["production_authority"] = source_paths.get(
        "production_qualification"
    )

    stage903 = payloads["stage903"]
    stage906 = payloads["stage906"]
    controller_heartbeat = payloads["controller_heartbeat"]
    stage923 = payloads["stage923"]
    stage924 = payloads["stage924"]
    stage925 = payloads["stage925"]
    stage932 = payloads["stage932"]
    kill_switch = payloads["kill_switch"]
    account_recovery_not_required = stage924.get("recovery_status") == "account_recovery_not_required_aligned"
    account_recovery_ack_suite_passed = (
        stage925.get("suite_status") == "account_recovery_ack_suite_passed_fail_closed"
        and _to_int(stage925.get("failed_count"), -1) == 0
        and _to_int(stage925.get("order_api_called_count"), -1) == 0
    )
    route_smoke_confirmed = (
        stage932.get("status") == "submit_cancel_confirmed"
        and _to_int(stage932.get("smoke_passed"), 0) == 1
        and _to_int(stage932.get("send_order_api_called_count"), -1) == 1
        and _to_int(stage932.get("cancel_order_api_called_count"), -1) == 1
        and _to_float(stage932.get("trade_volume"), -1.0) == 0.0
    )
    production_authority_valid = (
        authority.get("authority_status") == "production_authority_validated"
        and _strict_zero(authority.get("order_api_called_count"))
    )
    controller_heartbeat_age = _age_seconds(
        controller_heartbeat.get("heartbeat_at")
    )
    max_heartbeat_age = float(
        build_phase_d_config().hard_limits.max_heartbeat_age_seconds
    )
    stage903_path = source_paths.get("stage903")
    controller_heartbeat_valid = (
        bool(controller_heartbeat)
        and controller_heartbeat.get("target_date") == args.target_date
        and controller_heartbeat.get("mode") == "live-real"
        and controller_heartbeat.get("controller_status")
        == stage903.get("controller_status")
        and controller_heartbeat.get("kill_switch_active") is False
        and _strict_zero(controller_heartbeat.get("order_api_called_count"))
        and controller_heartbeat_age is not None
        and 0 <= controller_heartbeat_age <= max_heartbeat_age
        and stage903_path is not None
        and controller_heartbeat.get("summary_path")
        == str(stage903_path.resolve())
    )

    rows: list[dict[str, Any]] = []
    _check(
        rows,
        check="profile_is_current_c9",
        category="profile",
        passed=OFFICIAL_LIVE_FAMILY_VERSION == CURRENT_C9_FAMILY_VERSION,
        severity="block",
        observed=f"{OFFICIAL_LIVE_VERSION}/{OFFICIAL_LIVE_FAMILY_VERSION}",
        required=CURRENT_C9_FAMILY_VERSION,
        blocker="official_live_profile_not_c9",
    )
    _check(
        rows,
        check="acceptance_suite_passed_fail_closed",
        category="signed_production_authority",
        passed=production_authority_valid,
        severity="block",
        observed=authority,
        required="source-commit-bound production qualification + activation receipt + order_api=0",
        blocker="production_qualification_authority_not_validated",
    )
    _check(
        rows,
        check="completion_audit_proven",
        category="signed_production_authority",
        passed=production_authority_valid,
        severity="block",
        observed=authority,
        required="validated immutable manifest/qualification/activation chain",
        blocker="production_completion_authority_not_validated",
    )
    _check(
        rows,
        check="broker_shadow_reconcile_aligned",
        category="reconcile",
        passed=stage906.get("reconciliation_status") == "reconcile_aligned",
        severity="block",
        observed=(
            f"stage906={stage906.get('reconciliation_status', '')};"
            f"alignment={stage906.get('account_state_alignment', '')};"
            f"broker_rows={stage906.get('broker_position_rows', '')};"
            f"shadow_rows={stage906.get('shadow_position_rows', '')}"
        ),
        required="reconcile_aligned",
        blocker="broker_shadow_reconcile_not_aligned",
    )
    _check(
        rows,
        check="controller_not_killed_and_no_order_api",
        category="controller",
        passed=bool(stage903)
        and not bool(stage903.get("kill_switch_active"))
        and stage903.get("official_live_version") == OFFICIAL_LIVE_VERSION
        and _to_int(stage903.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"controller={stage903.get('controller_status', '')};"
            f"kill={stage903.get('kill_switch_active', '')};"
            f"live={stage903.get('official_live_version', '')};"
            f"order_api={stage903.get('order_api_called_count', '')}"
        ),
        required="latest controller evidence for current official live version + kill_switch_active=false + order_api=0",
        blocker="controller_evidence_not_armable",
    )
    _check(
        rows,
        check="controller_live_real_clean_ready",
        category="controller",
        passed=bool(stage903)
        and stage903.get("target_date") == args.target_date
        and stage903.get("mode") == "live-real"
        and stage903.get("controller_status") == "phase_d_controller_live_real_ready_no_submit_step"
        and stage903.get("stage905_executor_status") == "executor_dry_run_ready"
        and _to_int(stage903.get("stage905_blocked_count"), 999) == 0,
        severity="block",
        observed=(
            f"target={stage903.get('target_date', '')};"
            f"mode={stage903.get('mode', '')};"
            f"controller={stage903.get('controller_status', '')};"
            f"stage905={stage903.get('stage905_executor_status', '')};"
            f"stage905_blocked={stage903.get('stage905_blocked_count', '')}"
        ),
        required="same target_date + mode=live-real + controller live-real clean-ready + stage905 blocked=0",
        blocker="controller_not_live_real_clean_ready",
    )
    _check(
        rows,
        check="health_alive",
        category="health",
        passed=controller_heartbeat_valid,
        severity="block",
        observed=(
            f"controller={controller_heartbeat.get('controller_status', '')};"
            f"mode={controller_heartbeat.get('mode', '')};"
            f"age={controller_heartbeat_age};"
            f"order_api={controller_heartbeat.get('order_api_called_count', '')}"
        ),
        required="fresh same-target live-real controller heartbeat + exact summary path + order_api=0",
        blocker="controller_heartbeat_not_current_or_bound",
    )
    _check(
        rows,
        check="static_order_boundary_passed",
        category="signed_production_authority",
        passed=production_authority_valid,
        severity="block",
        observed=authority,
        required="qualified source tree includes required static order-boundary tests",
        blocker="production_static_authority_not_validated",
    )
    _check(
        rows,
        check="scheduler_dynamic_target_ready",
        category="signed_production_authority",
        passed=production_authority_valid,
        severity="block",
        observed=authority,
        required="Stage948-qualified production scheduler and launchd tests",
        blocker="production_scheduler_authority_not_validated",
    )
    _check(
        rows,
        check="no_unresolved_fail_closed_incident",
        category="incident",
        passed=stage923.get("incident_status") in {"phase_d_no_incident_monitor_only", "phase_d_no_incident_completion_proven"}
        and _to_int(stage923.get("operator_action_required"), -1) == 0
        and _to_int(stage923.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage923.get('incident_status', '')};"
            f"operator_required={stage923.get('operator_action_required', '')};"
            f"order_api={stage923.get('order_api_called_count', '')}"
        ),
        required="no unresolved incident + operator_action_required=0 + order_api=0",
        blocker="fail_closed_incident_still_open",
    )
    _check(
        rows,
        check="account_recovery_not_required",
        category="account_recovery",
        passed=stage924.get("recovery_status") == "account_recovery_not_required_aligned"
        and _to_int(stage924.get("operator_action_required"), -1) == 0
        and _to_int(stage924.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage924.get('recovery_status', '')};"
            f"operator_required={stage924.get('operator_action_required', '')};"
            f"order_api={stage924.get('order_api_called_count', '')}"
        ),
        required="account_recovery_not_required_aligned + operator_action_required=0 + order_api=0",
        blocker="account_recovery_still_required",
    )
    _check(
        rows,
        check="account_recovery_ack_suite_passed",
        category="account_recovery",
        passed=account_recovery_not_required or account_recovery_ack_suite_passed,
        severity="warn" if account_recovery_not_required else "block",
        observed=(
            f"stage924={stage924.get('recovery_status', '')};"
            f"status={stage925.get('suite_status', '')};"
            f"failed={stage925.get('failed_count', '')};"
            f"order_api={stage925.get('order_api_called_count', '')}"
        ),
        required="Stage924 no recovery required, or ack suite passed + failed=0 + order_api=0",
        blocker="account_recovery_ack_suite_not_passed_when_recovery_required",
    )
    _check(
        rows,
        check="one_lot_smoke_submit_cancel_confirmed",
        category="smoke",
        passed=route_smoke_confirmed,
        severity="warn",
        observed=(
            f"target={stage932.get('target_date', '')};"
            f"status={stage932.get('status', '')};"
            f"smoke_passed={stage932.get('smoke_passed', '')};"
            f"send={stage932.get('send_order_api_called_count', '')};"
            f"cancel={stage932.get('cancel_order_api_called_count', '')};"
            f"trade_volume={stage932.get('trade_volume', '')}"
        ),
        required="route-level smoke evidence if available; not required per target_date",
        blocker="stage932_clean_smoke_not_confirmed_route_warning",
    )
    _check(
        rows,
        check="aligned_idle_integration_passed",
        category="signed_production_authority",
        passed=production_authority_valid,
        severity="block",
        observed=authority,
        required="qualified aligned-idle regression bound to current source commit",
        blocker="production_integration_authority_not_validated",
    )
    _check(
        rows,
        check="kill_switch_inactive",
        category="kill_switch",
        passed=not _active(kill_switch),
        severity="block",
        observed=_active(kill_switch),
        required=False,
        blocker="kill_switch_active",
    )

    pre_env_checks = pd.DataFrame(rows)
    evidence_blockers = pre_env_checks[
        pre_env_checks["severity"].eq("block") & pre_env_checks["passed"].eq(0)
    ]
    pre_smoke_blockers = evidence_blockers[
        ~evidence_blockers["check"].eq("one_lot_smoke_submit_cancel_confirmed")
    ]
    evidence_blocker_count = int(len(evidence_blockers))
    pre_smoke_permitted = int(pre_smoke_blockers.empty)
    real_submit_env_enabled = _env_enabled(PHASE_D_REAL_ENABLED_ENV)
    confirm_live_real_ok = args.confirm_live_real == PHASE_D_CONFIRM_TEXT

    _check(
        rows,
        check="real_submit_env_not_enabled_while_blocked",
        category="arming_switch",
        passed=not (real_submit_env_enabled and evidence_blocker_count > 0),
        severity="block",
        observed=f"env={real_submit_env_enabled};evidence_blockers={evidence_blocker_count}",
        required="env must remain disabled while any evidence blocker exists",
        blocker="real_submit_env_enabled_before_armable",
    )
    _check(
        rows,
        check="real_submit_confirm_exact_when_enabled",
        category="arming_switch",
        passed=(not real_submit_env_enabled) or confirm_live_real_ok,
        severity="block",
        observed=f"env={real_submit_env_enabled};confirm_ok={confirm_live_real_ok}",
        required="exact confirm text is required when real-submit env is enabled",
        blocker="real_submit_confirm_missing_or_wrong",
    )
    _append_scope_capability_checks(
        rows,
        payloads=payloads,
        target_date=args.target_date,
        account_recovery_not_required=account_recovery_not_required,
        real_submit_env_enabled=real_submit_env_enabled,
        confirm_live_real_ok=confirm_live_real_ok,
    )

    checks = pd.DataFrame(rows)
    blocking_failures = checks[checks["severity"].eq("block") & checks["passed"].eq(0)]
    warn_failures = checks[checks["severity"].eq("warn") & checks["passed"].eq(0)]
    all_preconditions_passed = blocking_failures.empty
    real_submit_permitted = int(all_preconditions_passed and real_submit_env_enabled and confirm_live_real_ok)
    if real_submit_permitted:
        arming_status = "real_submit_arming_permitted_ready"
    elif all_preconditions_passed:
        arming_status = "real_submit_arming_ready_requires_explicit_enable"
    else:
        arming_status = "real_submit_arming_blocked_fail_closed"

    order_api_called = max(
        _to_int(stage903.get("order_api_called_count"), 0),
        _to_int(stage906.get("order_api_called_count"), 0),
        _to_int(controller_heartbeat.get("order_api_called_count"), 0),
        _to_int(authority.get("order_api_called_count"), 0),
        _to_int(stage923.get("order_api_called_count"), 0),
        _to_int(stage924.get("order_api_called_count"), 0),
        _to_int(stage925.get("order_api_called_count"), 0),
    )
    scope_evidence_inputs, scope_capabilities, scope_evidence_digest = (
        _build_scope_capabilities(
            checks=checks,
            payloads=payloads,
            source_paths=source_paths,
            target_date=args.target_date,
            real_submit_env_enabled=real_submit_env_enabled,
            confirm_live_real_ok=confirm_live_real_ok,
        )
    )
    reduce_close_submit_permitted = int(
        scope_capabilities["reduce_close"]["permitted"]
    )
    retry_open_submit_permitted = int(
        scope_capabilities["retry_open"]["permitted"]
    )
    initial_open_submit_permitted = int(
        scope_capabilities["initial_open"]["permitted"]
    )
    summary = {
        "model_tag": MODEL_TAG,
        "scope_capability_schema_version": SCOPE_CAPABILITY_SCHEMA_VERSION,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "execution_profile": C9_15W_PROFILE.profile_key,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
        "arming_status": arming_status,
        "real_submit_permitted": real_submit_permitted,
        "auto_submit_permitted": real_submit_permitted,
        "reduce_close_submit_permitted": reduce_close_submit_permitted,
        "retry_open_submit_permitted": retry_open_submit_permitted,
        "initial_open_submit_permitted": initial_open_submit_permitted,
        "scope_evidence_inputs": scope_evidence_inputs,
        "scope_capabilities": scope_capabilities,
        "scope_evidence_digest": scope_evidence_digest,
        "scope_evidence_digest_payload_fields": [
            "scope_evidence_inputs",
            "scope_capabilities",
        ],
        "pre_smoke_permitted": pre_smoke_permitted,
        "pre_smoke_blocking_failure_count": int(len(pre_smoke_blockers)),
        "pre_smoke_blocking_failures": pre_smoke_blockers.to_dict(orient="records"),
        "env_real_submit_enabled": int(real_submit_env_enabled),
        "confirm_live_real_ok": int(confirm_live_real_ok),
        "blocking_failure_count": int(len(blocking_failures)),
        "warn_failure_count": int(len(warn_failures)),
        "evidence_blocker_count_before_env": evidence_blocker_count,
        "order_api_called_count": int(order_api_called),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {key: str(value.resolve()) if value else "" for key, value in source_paths.items()},
        "judgement": {
            "overfit_before": "否。Stage927 只聚合执行证据，不改策略参数或样本。",
            "continue_before": "是。全自动必须有最终真实提交开关闸门。",
            "overfit_after": "否。闸门状态不反馈优化 C9。",
            "continue_after": "是。若仍 blocked，下一步处理真实账户/影子盘对账差异；若 ready，再进入最小真实 adapter 审查和显式启用。",
        },
    }
    checks.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
