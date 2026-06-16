from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_FAMILY_VERSION, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ENABLED_ENV,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage927_official_live_real_submit_arming_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage927_official_live_real_submit_arming_gate"
CURRENT_C9_FAMILY_VERSION = "stage819_c9_intraday_stop_retry"


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
            f"- Target date: `{summary['target_date']}`",
            f"- Arming status: `{summary['arming_status']}`",
            f"- Real submit permitted: `{summary['real_submit_permitted']}`",
            f"- Auto submit permitted: `{summary['auto_submit_permitted']}`",
            f"- Blockers: `{summary['blocking_failure_count']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
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
            "- Stage912 may pass while fail-closed. Stage927 requires completion, reconciliation, incident, recovery, scheduler, heartbeat, and static-boundary evidence before live arming.",
            "- Even with all evidence green, live submit still requires the real-submit env switch and the exact confirmation text.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D real-submit arming gate.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--confirm-live-real", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)

    source_paths: dict[str, Path | None] = {
        "stage903": _latest("qmt_roll_stage903_official_live_phase_d_controller_summary_*_stage903_official_live_phase_d_controller_v1.json"),
        "stage910": _latest("qmt_roll_stage910_official_live_phase_d_health_check_summary_*_stage910_official_live_phase_d_health_check_v1.json"),
        "stage912": _latest("qmt_roll_stage912_official_live_phase_d_acceptance_suite_summary_*_stage912_official_live_phase_d_acceptance_suite_v1.json"),
        "stage913": _latest("qmt_roll_stage913_official_live_phase_d_completion_audit_summary_*_stage913_official_live_phase_d_completion_audit_v1.json"),
        "stage916": _latest("qmt_roll_stage916_official_live_order_boundary_static_audit_summary_*_stage916_official_live_order_boundary_static_audit_v1.json"),
        "stage921": _latest("qmt_roll_stage921_official_live_scheduler_audit_summary_*_stage921_official_live_scheduler_audit_v1.json"),
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
        "stage926": _latest("qmt_roll_stage926_official_live_aligned_idle_integration_summary_*_stage926_official_live_aligned_idle_integration_v1.json"),
        "stage932": _latest("qmt_roll_stage932_official_live_ctp_smoke_order_summary_*_stage932_official_live_ctp_smoke_order_v1.json"),
        "kill_switch": KILL_SWITCH_PATH if KILL_SWITCH_PATH.exists() else None,
    }
    payloads = {name: _read_json(path) for name, path in source_paths.items()}

    stage903 = payloads["stage903"]
    stage906 = payloads["stage906"]
    stage910 = payloads["stage910"]
    stage912 = payloads["stage912"]
    stage913 = payloads["stage913"]
    stage916 = payloads["stage916"]
    stage921 = payloads["stage921"]
    stage923 = payloads["stage923"]
    stage924 = payloads["stage924"]
    stage925 = payloads["stage925"]
    stage926 = payloads["stage926"]
    stage932 = payloads["stage932"]
    kill_switch = payloads["kill_switch"]

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
        category="acceptance",
        passed=stage912.get("suite_status") == "phase_d_acceptance_passed_fail_closed"
        and _to_int(stage912.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=f"status={stage912.get('suite_status', '')};order_api={stage912.get('order_api_called_count', '')}",
        required="phase_d_acceptance_passed_fail_closed + order_api=0",
        blocker="stage912_acceptance_not_passed",
    )
    _check(
        rows,
        check="completion_audit_proven",
        category="completion",
        passed=stage913.get("completion_status") == "phase_d_completion_proven"
        and _to_int(stage913.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage913.get('completion_status', '')};"
            f"passed={stage913.get('passed_count', '')};"
            f"partial={stage913.get('partial_count', '')};"
            f"incomplete={stage913.get('incomplete_count', '')};"
            f"order_api={stage913.get('order_api_called_count', '')}"
        ),
        required="phase_d_completion_proven + no partial/incomplete requirements + order_api=0",
        blocker="phase_d_completion_not_proven",
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
        check="health_alive",
        category="health",
        passed=stage910.get("health_status") in {"controller_alive_fail_closed", "controller_alive_ready"}
        and _to_int(stage910.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"health={stage910.get('health_status', '')};"
            f"controller={stage910.get('controller_status', '')};"
            f"age={stage910.get('heartbeat_age_seconds', '')};"
            f"order_api={stage910.get('order_api_called_count', '')}"
        ),
        required="controller alive health status + order_api=0",
        blocker="health_not_alive",
    )
    _check(
        rows,
        check="static_order_boundary_passed",
        category="order_boundary",
        passed=stage916.get("static_audit_status") == "phase_d_order_boundary_static_audit_passed"
        and _to_int(stage916.get("disallowed_reference_count"), -1) == 0
        and _to_int(stage916.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage916.get('static_audit_status', '')};"
            f"disallowed={stage916.get('disallowed_reference_count', '')};"
            f"order_api={stage916.get('order_api_called_count', '')}"
        ),
        required="static audit passed + disallowed=0 + order_api=0",
        blocker="static_order_boundary_not_passed",
    )
    _check(
        rows,
        check="scheduler_dynamic_target_ready",
        category="scheduler",
        passed=stage921.get("scheduler_status") == "scheduler_template_dynamic_target_ready_fail_closed"
        and _to_int(stage921.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage921.get('scheduler_status', '')};"
            f"target_mode={stage921.get('target_date_mode', '')};"
            f"order_api={stage921.get('order_api_called_count', '')}"
        ),
        required="dynamic latest-completed scheduler template ready + order_api=0",
        blocker="scheduler_not_dynamic_ready",
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
        passed=stage925.get("suite_status") == "account_recovery_ack_suite_passed_fail_closed"
        and _to_int(stage925.get("failed_count"), -1) == 0
        and _to_int(stage925.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage925.get('suite_status', '')};"
            f"failed={stage925.get('failed_count', '')};"
            f"order_api={stage925.get('order_api_called_count', '')}"
        ),
        required="ack suite passed + failed=0 + order_api=0",
        blocker="account_recovery_ack_suite_not_passed",
    )
    _check(
        rows,
        check="one_lot_smoke_submit_cancel_confirmed",
        category="smoke",
        passed=stage932.get("target_date") == args.target_date
        and stage932.get("status") == "submit_cancel_confirmed"
        and _to_int(stage932.get("smoke_passed"), 0) == 1
        and _to_int(stage932.get("send_order_api_called_count"), -1) == 1
        and _to_int(stage932.get("cancel_order_api_called_count"), -1) == 1
        and _to_float(stage932.get("trade_volume"), -1.0) == 0.0,
        severity="block",
        observed=(
            f"target={stage932.get('target_date', '')};"
            f"status={stage932.get('status', '')};"
            f"smoke_passed={stage932.get('smoke_passed', '')};"
            f"send={stage932.get('send_order_api_called_count', '')};"
            f"cancel={stage932.get('cancel_order_api_called_count', '')};"
            f"trade_volume={stage932.get('trade_volume', '')}"
        ),
        required="same target_date + submit_cancel_confirmed + smoke_passed=1 + send=1 + cancel=1 + trade_volume=0",
        blocker="stage932_clean_smoke_not_confirmed",
    )
    _check(
        rows,
        check="aligned_idle_integration_passed",
        category="integration",
        passed=stage926.get("idle_integration_status") == "aligned_idle_no_action_passed_fail_closed"
        and _to_int(stage926.get("real_snapshot_restored"), -1) == 1
        and _to_int(stage926.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=(
            f"status={stage926.get('idle_integration_status', '')};"
            f"restored={stage926.get('real_snapshot_restored', '')};"
            f"order_api={stage926.get('order_api_called_count', '')}"
        ),
        required="aligned idle integration proof passed + restored=1 + order_api=0",
        blocker="aligned_idle_integration_not_passed",
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
        _to_int(stage910.get("order_api_called_count"), 0),
        _to_int(stage912.get("order_api_called_count"), 0),
        _to_int(stage913.get("order_api_called_count"), 0),
        _to_int(stage916.get("order_api_called_count"), 0),
        _to_int(stage921.get("order_api_called_count"), 0),
        _to_int(stage923.get("order_api_called_count"), 0),
        _to_int(stage924.get("order_api_called_count"), 0),
        _to_int(stage925.get("order_api_called_count"), 0),
        _to_int(stage926.get("order_api_called_count"), 0),
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "arming_status": arming_status,
        "real_submit_permitted": real_submit_permitted,
        "auto_submit_permitted": real_submit_permitted,
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
