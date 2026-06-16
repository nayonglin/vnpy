from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_FAMILY_VERSION,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    CONTROLLER_HEARTBEAT_PATH,
    KILL_SWITCH_PATH,
    READONLY_SUMMARY_PATH,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage913_official_live_phase_d_completion_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage913_official_live_phase_d_completion_audit"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "requirements_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_requirements_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: Path | None) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _latest(pattern: str) -> Path | None:
    rows = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _target_date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _target_summary(prefix: str, target_date: str, model_tag: str) -> Path | None:
    date_key = _target_date_key(target_date)
    path = OUTPUT_DIR / f"{prefix}_summary_{date_key}_{model_tag}.json"
    return path if path.exists() else None


def _status_rank(status: str) -> int:
    return {
        "passed": 0,
        "partial": 1,
        "not_proven": 2,
        "blocked": 3,
        "missing": 4,
        "failed": 5,
    }.get(status, 5)


def _row(
    rows: list[dict[str, Any]],
    *,
    requirement_id: str,
    requirement: str,
    status: str,
    evidence: str,
    observed: Any,
    required: Any,
    next_action: str,
) -> None:
    rows.append(
        {
            "requirement_id": requirement_id,
            "requirement": requirement,
            "status": status,
            "evidence": evidence,
            "observed": observed,
            "required": required,
            "next_action": next_action,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


def _active(payload: dict[str, Any]) -> bool:
    return bool(payload.get("enabled", False) or payload.get("kill_switch_active", False))


def _to_int(value: Any, default: int = -1) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _build_report(summary: dict[str, Any], requirements: pd.DataFrame) -> str:
    blocked = requirements[requirements["status"].isin(["blocked", "missing", "failed", "not_proven"])]
    blocked_md = blocked.to_markdown(index=False) if not blocked.empty else "_empty_"
    all_md = requirements.to_markdown(index=False) if not requirements.empty else "_empty_"
    return "\n".join(
        [
            "# Stage913 Official Live Phase D Completion Audit",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- completion 状态：`{summary['completion_status']}`",
            f"- passed：`{summary['passed_count']}`",
            f"- partial：`{summary['partial_count']}`",
            f"- blocked/not_proven/missing/failed：`{summary['incomplete_count']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Incomplete Requirements",
            "",
            blocked_md,
            "",
            "## All Requirements",
            "",
            all_md,
            "",
            "## 说明",
            "",
            "- Stage913 是目标级完成审计，不连接 CTP，不提交委托。",
            "- `partial` 表示架构存在但证据还不足以证明无人值守实盘可用。",
            "- 只有所有要求均 `passed` 且 order API 仍受控，才能声称 Phase D 全自动完成。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D completion audit.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    target_date = args.target_date

    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    kill_switch = _read_json(KILL_SWITCH_PATH)
    heartbeat = _read_json(CONTROLLER_HEARTBEAT_PATH)

    stage903_path = _latest("qmt_roll_stage903_official_live_phase_d_controller_summary_*_stage903_official_live_phase_d_controller_v1.json")
    stage910_path = _latest("qmt_roll_stage910_official_live_phase_d_health_check_summary_*_stage910_official_live_phase_d_health_check_v1.json")
    stage912_path = _latest("qmt_roll_stage912_official_live_phase_d_acceptance_suite_summary_*_stage912_official_live_phase_d_acceptance_suite_v1.json")
    stage912_checks_path = _latest("qmt_roll_stage912_official_live_phase_d_acceptance_suite_checks_*_stage912_official_live_phase_d_acceptance_suite_v1.csv")
    stage914_path = _latest("qmt_roll_stage914_official_live_ctp_runtime_preflight_summary_*_stage914_official_live_ctp_runtime_preflight_v1.json")
    stage915_path = _latest("qmt_roll_stage915_official_live_submit_adapter_boundary_suite_summary_*_stage915_official_live_submit_adapter_boundary_suite_v1.json")
    stage916_path = _latest("qmt_roll_stage916_official_live_order_boundary_static_audit_summary_*_stage916_official_live_order_boundary_static_audit_v1.json")
    stage917_path = _latest("qmt_roll_stage917_official_live_mock_broker_integration_summary_*_stage917_official_live_mock_broker_integration_v1.json")
    stage918_path = _target_summary(
        "qmt_roll_stage918_official_live_reconcile_policy_audit",
        target_date,
        "stage918_official_live_reconcile_policy_audit_v1",
    )
    stage919_path = _target_summary(
        "qmt_roll_stage919_official_live_reconcile_attribution_audit",
        target_date,
        "stage919_official_live_reconcile_attribution_audit_v1",
    )
    stage920_path = _target_summary(
        "qmt_roll_stage920_official_live_account_sync_gate",
        target_date,
        "stage920_official_live_account_sync_gate_v1",
    )
    stage921_path = _latest("qmt_roll_stage921_official_live_scheduler_audit_summary_*_stage921_official_live_scheduler_audit_v1.json")
    stage922_path = _latest("qmt_roll_stage922_official_live_target_date_resolver_summary_*_stage922_official_live_target_date_resolver_v1.json")
    stage923_path = _target_summary(
        "qmt_roll_stage923_official_live_fail_closed_incident",
        target_date,
        "stage923_official_live_fail_closed_incident_v1",
    )
    stage924_path = _target_summary(
        "qmt_roll_stage924_official_live_account_recovery_gate",
        target_date,
        "stage924_official_live_account_recovery_gate_v1",
    )
    stage925_path = _target_summary(
        "qmt_roll_stage925_official_live_account_recovery_ack_suite",
        target_date,
        "stage925_official_live_account_recovery_ack_suite_v1",
    )
    stage926_path = _latest(
        "qmt_roll_stage926_official_live_aligned_idle_integration_summary_*_stage926_official_live_aligned_idle_integration_v1.json"
    )
    stage927_path = _target_summary(
        "qmt_roll_stage927_official_live_real_submit_arming_gate",
        target_date,
        "stage927_official_live_real_submit_arming_gate_v1",
    )

    stage909_path = _target_summary(
        "qmt_roll_stage909_official_live_shadow_refresh_gate",
        target_date,
        "stage909_official_live_shadow_refresh_gate_v1",
    )
    stage260_path = _target_summary(
        "qmt_roll_stage260_official_live_daily_execution_gate",
        target_date,
        "stage260_official_live_daily_execution_gate_v1",
    )
    stage902_path = _target_summary(
        "qmt_roll_stage902_official_live_phase_d_readiness_gate",
        target_date,
        "stage902_official_live_phase_d_readiness_gate_v1",
    )
    stage904_path = _target_summary(
        "qmt_roll_stage904_official_live_c9_intraday_monitor",
        target_date,
        "stage904_official_live_c9_intraday_monitor_v1",
    )
    stage905_path = _target_summary(
        "qmt_roll_stage905_official_live_executor_dry_run",
        target_date,
        "stage905_official_live_executor_dry_run_v1",
    )
    stage906_path = _target_summary(
        "qmt_roll_stage906_official_live_reconciliation_worker",
        target_date,
        "stage906_official_live_reconciliation_worker_v1",
    )
    stage908_path = _target_summary(
        "qmt_roll_stage908_official_live_submit_adapter_contract",
        target_date,
        "stage908_official_live_submit_adapter_contract_v1",
    )

    stage903 = _read_json(stage903_path)
    stage909 = _read_json(stage909_path)
    stage260 = _read_json(stage260_path)
    stage902 = _read_json(stage902_path)
    stage904 = _read_json(stage904_path)
    stage905 = _read_json(stage905_path)
    stage906 = _read_json(stage906_path)
    stage908 = _read_json(stage908_path)
    stage910 = _read_json(stage910_path)
    stage912 = _read_json(stage912_path)
    stage912_checks = _read_csv_maybe(stage912_checks_path)
    stage914 = _read_json(stage914_path)
    stage915 = _read_json(stage915_path)
    stage916 = _read_json(stage916_path)
    stage917 = _read_json(stage917_path)
    stage918 = _read_json(stage918_path)
    stage919 = _read_json(stage919_path)
    stage920 = _read_json(stage920_path)
    stage921 = _read_json(stage921_path)
    stage922 = _read_json(stage922_path)
    stage923 = _read_json(stage923_path)
    stage924 = _read_json(stage924_path)
    stage925 = _read_json(stage925_path)
    stage926 = _read_json(stage926_path)
    stage927 = _read_json(stage927_path)

    reconcile_aligned = stage906.get("reconciliation_status") == "reconcile_aligned"
    stage260_executable_count = _to_int(stage260.get("executable_count"), 0)
    stage260_blocked_count = _to_int(stage260.get("blocked_count"), 0)
    stage260_mismatch_count = _to_int(stage260.get("skipped_position_mismatch_count"), 0)
    stage260_order_api_count = _to_int(stage260.get("order_api_called_count"), 0)
    execution_gate_idle_pass = (
        bool(stage260)
        and bool(stage902)
        and reconcile_aligned
        and stage260_executable_count == 0
        and stage260_blocked_count == 0
        and stage260_mismatch_count == 0
        and stage260_order_api_count == 0
        and stage902.get("overall_status") in {
            "phase_d_readiness_dry_run_passed_real_still_disabled",
            "phase_d_readiness_ready_for_real_submit",
        }
    )
    execution_gate_ready_pass = (
        stage260_executable_count > 0
        and _to_int(stage902.get("ready_for_phase_d_real"), 0) == 1
        and stage260_order_api_count == 0
    )
    executor_idle_pass = (
        stage905.get("executor_status") == "executor_no_intents"
        and execution_gate_idle_pass
    )

    rows: list[dict[str, Any]] = []
    _row(
        rows,
        requirement_id="profile",
        requirement="当前官方 live default 必须解析为 C9",
        status="passed" if OFFICIAL_LIVE_FAMILY_VERSION == "stage819_c9_intraday_stop_retry" else "blocked",
        evidence="qmt_roll_official_live_config.py",
        observed=f"{OFFICIAL_LIVE_VERSION}/{OFFICIAL_LIVE_FAMILY_VERSION}",
        required="stage819_c9_intraday_stop_retry family",
        next_action="若不为 C9，禁止进入 Phase D。",
    )
    target_shadow_ready = (
        official_summary.get("analysis_end") == target_date
        and official_summary.get("analysis_start") == OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
    )
    target_shadow_refresh_proven = stage909.get("shadow_refresh_status") == "shadow_refresh_completed"
    target_shadow_auto_skip_ready = (
        stage903.get("stage922_resolver_status") == "target_date_resolved_local_shadow_ready_fail_closed"
        and stage903.get("stage909_effective_shadow_refresh_mode") == "plan-only"
    )
    _row(
        rows,
        requirement_id="signal",
        requirement="信号计算链路存在且目标日期 shadow 可读取",
        status=(
            "passed"
            if target_shadow_ready and (target_shadow_refresh_proven or target_shadow_auto_skip_ready)
            else "partial"
            if target_shadow_ready and stage909.get("shadow_refresh_status") == "shadow_refresh_plan_only"
            else "blocked"
        ),
        evidence=f"{OFFICIAL_LIVE_SUMMARY_PATH}; {stage909_path}",
        observed=(
            f"analysis_end={official_summary.get('analysis_end', '')};"
            f"analysis_start={official_summary.get('analysis_start', '')};"
            f"stage909={stage909.get('shadow_refresh_status', '')};"
            f"attempted={stage909.get('refresh_attempted', '')};"
            f"controller_effective_shadow={stage903.get('stage909_effective_shadow_refresh_mode', '')};"
            f"stage922={stage903.get('stage922_resolver_status', '')}"
        ),
        required=(
            "target-date shadow present with "
            f"analysis_start={OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE}; completed refresh or auto-skip because local shadow is already ready"
        ),
        next_action="打开 shadow refresh gate 并在日终数据完成后运行 Stage909 --mode run。",
    )
    _row(
        rows,
        requirement_id="target_date_resolver",
        requirement="无人值守运行必须能解析最新已完成交易日，且不能把日期解析当成下单许可",
        status=(
            "passed"
            if stage922.get("resolver_status")
            in {
                "target_date_resolved_requires_refresh_fail_closed",
                "target_date_resolved_local_shadow_ready_fail_closed",
                "target_date_before_live_shadow_start_waiting_fail_closed",
            }
            and _to_int(stage922.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage922.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage922
            else "missing"
        ),
        evidence=str(stage922_path),
        observed=(
            f"stage922={stage922.get('resolver_status', '')};"
            f"resolved={stage922.get('resolved_target_date', '')};"
            f"requires_shadow_refresh={stage922.get('requires_shadow_refresh', '')};"
            f"order_api={stage922.get('order_api_called_count', '')}"
        ),
        required="latest-completed resolver exists + auto_submit_permitted=0 + order_api=0",
        next_action="由 Stage903 latest-completed 模式调用 Stage922；Stage909 刷新未命中前保持 fail-closed。",
    )
    readonly_state = readonly_summary.get("broker_snapshot", {}).get("position_snapshot_state", "")
    readonly_age = stage906.get("readonly_snapshot_age_seconds")
    readonly_ready = (
        readonly_summary.get("status") == "readonly_snapshots_received"
        and readonly_state in {"confirmed_flat", "positions_received"}
        and (
            pd.isna(pd.to_numeric(readonly_age, errors="coerce"))
            or float(pd.to_numeric(readonly_age, errors="coerce")) <= 300
        )
    )
    _row(
        rows,
        requirement_id="broker_state",
        requirement="broker 只读快照 fresh 且持仓状态明确",
        status="passed" if readonly_ready else "blocked",
        evidence=f"{READONLY_SUMMARY_PATH}; {stage902_path}",
        observed=(
            f"readonly={readonly_summary.get('status', '')};position_state={readonly_state};"
            f"stage902={stage902.get('overall_status', '')};age={readonly_age}"
        ),
        required="readonly_snapshots_received + confirmed_flat/positions_received + age<=300 when measured",
        next_action="按 Stage907 production-live refresh gate 运行只读 CTP 快照；不得下单。",
    )
    _row(
        rows,
        requirement_id="production_ctp_runtime_preflight",
        requirement="production-live CTP env 与 vnpy_ctp runtime 选择可机器审计",
        status=(
            "passed"
            if stage914.get("preflight_status") == "production_readonly_preflight_passed"
            and _to_int(stage914.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage914
            else "missing"
        ),
        evidence=str(stage914_path),
        observed=f"stage914={stage914.get('preflight_status', '')};blockers={stage914.get('blocking_failure_count', '')};order_api={stage914.get('order_api_called_count', '')}",
        required="production_readonly_preflight_passed + order_api_called_count=0",
        next_action="预检通过后，仍需 Stage907 refresh gate 显式确认才能连接 CTP 只读。",
    )
    _row(
        rows,
        requirement_id="execution_gate",
        requirement="Stage260/Stage251/Stage902 执行闸门能给出可执行或明确阻断",
        status=(
            "passed"
            if execution_gate_ready_pass or execution_gate_idle_pass
            else "partial"
            if stage260 and stage902 and _to_int(stage260.get("order_api_called_count"), 0) == 0
            else "missing"
        ),
        evidence=f"{stage260_path}; {stage902_path}",
        observed=(
            f"stage260_executable={stage260.get('executable_count', '')};"
            f"stage260_blocked={stage260.get('blocked_count', '')};"
            f"stage260_mismatch={stage260.get('skipped_position_mismatch_count', '')};"
            f"reconcile={stage906.get('reconciliation_status', '')};"
            f"stage902={stage902.get('overall_status', '')}"
        ),
        required="fresh broker state makes executable decisions or reconciled no-action idle; order API remains 0 before submit",
        next_action="fresh broker snapshot 后重跑 Stage260/251/902。",
    )
    _row(
        rows,
        requirement_id="intraday_monitor",
        requirement="C9 入场日 0.5R 盘中监控可使用 fresh tick",
        status=(
            "passed"
            if stage904.get("monitor_status") in {"intraday_monitor_ready", "intraday_monitor_close_dry_run"} and stage903.get("env_gates", {}).get("OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED")
            else "partial"
            if stage904
            else "missing"
        ),
        evidence=str(stage904_path),
        observed=f"stage904={stage904.get('monitor_status', '')};close_dry_run={stage904.get('close_dry_run_count', '')};session_daemon={stage903.get('env_gates', {}).get('OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED', '')}",
        required="fresh tick + session daemon enabled + monitor not blocked",
        next_action="接入 fresh tick/session daemon；不能用历史收盘价代替实时触发。",
    )
    _row(
        rows,
        requirement_id="executor",
        requirement="executor intent 能在无阻断时生成可提交前 payload",
        status=(
            "passed"
            if (
                stage905.get("executor_status") == "executor_dry_run_ready"
                and _to_int(stage905.get("ready_count"), 0) > 0
            )
            or executor_idle_pass
            else "partial"
            if stage905
            else "missing"
        ),
        evidence=str(stage905_path),
        observed=(
            f"stage905={stage905.get('executor_status', '')};"
            f"ready={stage905.get('ready_count', '')};"
            f"blocked={stage905.get('blocked_count', '')};"
            f"idle_pass={executor_idle_pass};"
            f"reconcile={stage906.get('reconciliation_status', '')}"
        ),
        required="executor_dry_run_ready + ready_count>0, or reconciled no-action idle",
        next_action="broker/contract/position/Stage260 通过后重跑 Stage905。",
    )
    _row(
        rows,
        requirement_id="reconcile",
        requirement="shadow、broker、intent 对账一致",
        status="passed" if stage906.get("reconciliation_status") == "reconcile_aligned" else "blocked" if stage906 else "missing",
        evidence=str(stage906_path),
        observed=f"stage906={stage906.get('reconciliation_status', '')};alignment={stage906.get('account_state_alignment', '')}",
        required="reconcile_aligned",
        next_action="fresh broker positions/orders/trades 后重跑 Stage906；不得用 shadow 回填 broker。",
    )
    _row(
        rows,
        requirement_id="adapter",
        requirement="下单 adapter 合约通过但真实提交仍受 gate 控制",
        status=(
            "passed"
            if stage908.get("adapter_contract_status")
            in {
                "adapter_contract_ready_for_external_live_adapter_review",
                "adapter_contract_no_intents_idle",
            }
            else "partial"
            if stage908
            else "missing"
        ),
        evidence=str(stage908_path),
        observed=f"stage908={stage908.get('adapter_contract_status', '')};live_submit_permitted={stage908.get('live_submit_permitted', '')}",
        required="adapter contract ready; live adapter reviewed separately",
        next_action="前置 gate 全过后再做真实 adapter code review 和最小 smoke 流程。",
    )
    _row(
        rows,
        requirement_id="submit_adapter_boundary",
        requirement="真实提交边界有可回归的 fail-closed/FakeMainEngine 验收",
        status=(
            "passed"
            if stage915.get("adapter_boundary_status") == "phase_d_submit_adapter_boundary_passed"
            and _to_int(stage915.get("real_broker_order_api_called_count"), -1) == 0
            else "blocked"
            if stage915
            else "missing"
        ),
        evidence=str(stage915_path),
        observed=f"stage915={stage915.get('adapter_boundary_status', '')};fake_send={stage915.get('fake_send_order_called_count', '')};real_order_api={stage915.get('real_broker_order_api_called_count', '')}",
        required="boundary suite passed + real_broker_order_api_called_count=0",
        next_action="真实 broker adapter 仍需 fresh broker 快照、对账通过和最小 smoke/review 后再启用。",
    )
    _row(
        rows,
        requirement_id="order_boundary_static_audit",
        requirement="Phase D 只有受控 adapter/FakeMainEngine 出现 order API 边界",
        status=(
            "passed"
            if stage916.get("static_audit_status") == "phase_d_order_boundary_static_audit_passed"
            and _to_int(stage916.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage916
            else "missing"
        ),
        evidence=str(stage916_path),
        observed=f"stage916={stage916.get('static_audit_status', '')};allowed_send={stage916.get('allowed_send_order_reference_count', '')};disallowed={stage916.get('disallowed_reference_count', '')}",
        required="static audit passed + disallowed_reference_count=0",
        next_action="每次改 Phase D 文件后复跑 Stage916。",
    )
    _row(
        rows,
        requirement_id="mock_broker_integration_proof",
        requirement="mock fresh broker 状态下 signal/gate/executor/reconcile 链路可闭合且恢复真实文件",
        status=(
            "passed"
            if stage917.get("mock_integration_status") == "mock_broker_state_gate_reconcile_passed_real_submit_still_blocked"
            and _to_int(stage917.get("order_api_called_count"), -1) == 0
            and _to_int(stage917.get("real_snapshot_restored"), 0) == 1
            else "blocked"
            if stage917
            else "missing"
        ),
        evidence=str(stage917_path),
        observed=(
            f"stage917={stage917.get('mock_integration_status', '')};"
            f"restored={stage917.get('real_snapshot_restored', '')};"
            f"order_api={stage917.get('order_api_called_count', '')}"
        ),
        required="mock proof passed + restored=1 + order_api=0",
        next_action="mock 通过后仍需生产 CTP fresh read-only 快照下重跑 Stage260/902/905/906。",
    )
    _row(
        rows,
        requirement_id="aligned_idle_integration_proof",
        requirement="broker/shadow 对齐且无可执行订单时，控制链路必须自动空跑且不生成订单",
        status=(
            "passed"
            if stage926.get("idle_integration_status") == "aligned_idle_no_action_passed_fail_closed"
            and _to_int(stage926.get("real_snapshot_restored"), 0) == 1
            and _to_int(stage926.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage926
            else "missing"
        ),
        evidence=str(stage926_path),
        observed=(
            f"stage926={stage926.get('idle_integration_status', '')};"
            f"restored={stage926.get('real_snapshot_restored', '')};"
            f"order_api={stage926.get('order_api_called_count', '')};"
            f"child={stage926.get('child_statuses', '')}"
        ),
        required="aligned idle proof passed + restored=1 + order_api=0",
        next_action="每次修改 Stage260/902/904/905/906/908 idle 语义后复跑 Stage926。",
    )
    _row(
        rows,
        requirement_id="reconcile_policy",
        requirement="broker/shadow 差异必须产出 fail-closed reconcile policy，而不是无人值守提交",
        status=(
            "passed"
            if stage918.get("policy_status")
            in {
                "reconcile_policy_aligned_no_action",
                "reconcile_policy_manual_only_reduce_candidate_fail_closed",
                "reconcile_policy_blocked_fail_closed",
            }
            and _to_int(stage918.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage918.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage918
            else "missing"
        ),
        evidence=str(stage918_path),
        observed=(
            f"stage918={stage918.get('policy_status', '')};"
            f"manual_candidates={stage918.get('manual_action_candidate_count', '')};"
            f"auto_submit={stage918.get('auto_submit_permitted', '')};"
            f"order_api={stage918.get('order_api_called_count', '')}"
        ),
        required="reconcile policy exists + auto_submit_permitted=0 when divergent + order_api=0",
        next_action="若要支持 reduce-only reconciliation mode，必须另做人工确认和单独晋升。",
    )
    _row(
        rows,
        requirement_id="reconcile_attribution",
        requirement="broker/shadow 差异必须有来源归因审计，未解释前保持 fail-closed",
        status=(
            "passed"
            if stage919.get("attribution_status")
            in {
                "reconcile_attribution_aligned",
                "reconcile_attribution_divergent_origin_unresolved_fail_closed",
                "reconcile_attribution_blocked_fail_closed",
            }
            and _to_int(stage919.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage919.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage919
            else "missing"
        ),
        evidence=str(stage919_path),
        observed=(
            f"stage919={stage919.get('attribution_status', '')};"
            f"divergent={stage919.get('divergent_count', '')};"
            f"auto_submit={stage919.get('auto_submit_permitted', '')};"
            f"order_api={stage919.get('order_api_called_count', '')}"
        ),
        required="attribution audit exists + divergent account origin blocks unattended submit + order_api=0",
        next_action="人工确认真实账户来源；未确认前不得把 reduce-only 差异处理升为无人值守。",
    )
    _row(
        rows,
        requirement_id="account_sync_guard",
        requirement="账户起点同步必须有机器可审计闸门；未同步时不能无人值守提交",
        status=(
            "passed"
            if stage920.get("account_sync_status")
            in {
                "account_sync_aligned_auto_progress_allowed",
                "account_sync_manual_ack_recorded_fail_closed",
                "account_sync_ack_invalid_fail_closed",
                "account_sync_operator_ack_required_fail_closed",
            }
            and _to_int(stage920.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage920.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage920
            else "missing"
        ),
        evidence=str(stage920_path),
        observed=(
            f"stage920={stage920.get('account_sync_status', '')};"
            f"divergent={stage920.get('divergent_count', '')};"
            f"ack_valid={stage920.get('ack_valid', '')};"
            f"order_api={stage920.get('order_api_called_count', '')}"
        ),
        required="account sync gate exists + unresolved divergence remains fail-closed + order_api=0",
        next_action="真实账户来源人工确认后，使用 Stage920 ack 文件记录起点决策，再重新跑 broker/shadow 对账。",
    )
    _row(
        rows,
        requirement_id="scheduler",
        requirement="后台调度必须有可审计的常驻控制器模板，并能处理无人值守日更目标日期",
        status=(
            "passed"
            if stage921.get("scheduler_status") == "scheduler_template_dynamic_target_ready_fail_closed"
            and _to_int(stage921.get("order_api_called_count"), -1) == 0
            else "partial"
            if stage921 and _to_int(stage921.get("order_api_called_count"), -1) == 0
            else "missing"
        ),
        evidence=str(stage921_path),
        observed=(
            f"stage921={stage921.get('scheduler_status', '')};"
            f"target_mode={stage921.get('target_date_mode', '')};"
            f"poll={stage921.get('poll_seconds', '')};"
            f"order_api={stage921.get('order_api_called_count', '')}"
        ),
        required="persistent launchd/controller loop + dynamic target-date handling + order_api=0",
        next_action="补 latest-completed-trading-day resolver 或生产 wrapper，避免 launchd 固定单日 target-date。",
    )
    _row(
        rows,
        requirement_id="fail_closed_incident",
        requirement="fail-closed 时必须自动生成可审计的人工处理事件包",
        status=(
            "passed"
            if stage923.get("incident_status")
            in {
                "phase_d_fail_closed_operator_attention_required",
                "phase_d_no_incident_monitor_only",
                "phase_d_no_incident_completion_proven",
            }
            and _to_int(stage923.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage923.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage923
            else "missing"
        ),
        evidence=str(stage923_path),
        observed=(
            f"stage923={stage923.get('incident_status', '')};"
            f"operator_required={stage923.get('operator_action_required', '')};"
            f"order_api={stage923.get('order_api_called_count', '')}"
        ),
        required="incident package exists when fail-closed + auto_submit_permitted=0 + order_api=0",
        next_action="把 Stage923 纳入常驻控制器和运维通知；人工处理后复跑全链路。",
    )
    _row(
        rows,
        requirement_id="account_recovery_gate",
        requirement="人工处理 broker/shadow 差异后，必须通过恢复闸门重新入链",
        status=(
            "passed"
            if stage924.get("recovery_status")
            in {
                "account_recovery_ack_required_fail_closed",
                "account_recovery_manual_keep_fail_closed",
                "account_recovery_manual_action_pending_fail_closed",
                "account_recovery_manual_action_done_rerun_required",
                "account_recovery_non_strategy_position_ack_recorded_fail_closed",
                "account_recovery_not_required_aligned",
            }
            and _to_int(stage924.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage924.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage924
            else "missing"
        ),
        evidence=str(stage924_path),
        observed=(
            f"stage924={stage924.get('recovery_status', '')};"
            f"operator_required={stage924.get('operator_action_required', '')};"
            f"ack_valid={stage924.get('ack_valid', '')};"
            f"order_api={stage924.get('order_api_called_count', '')}"
        ),
        required="recovery gate exists + auto_submit_permitted=0 + order_api=0",
        next_action="人工处理后，先跑 Stage924，再重跑 shadow/readonly/reconcile/Stage913。",
    )
    _row(
        rows,
        requirement_id="account_recovery_ack_suite",
        requirement="恢复确认文件必须覆盖错误确认、有效确认和手工处理后重跑语义",
        status=(
            "passed"
            if stage925.get("suite_status") == "account_recovery_ack_suite_passed_fail_closed"
            and _to_int(stage925.get("failed_count"), -1) == 0
            and _to_int(stage925.get("auto_submit_permitted"), -1) == 0
            and _to_int(stage925.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage925
            else "missing"
        ),
        evidence=str(stage925_path),
        observed=(
            f"stage925={stage925.get('suite_status', '')};"
            f"cases={stage925.get('case_count', '')};"
            f"failed={stage925.get('failed_count', '')};"
            f"auto_submit={stage925.get('auto_submit_permitted', '')};"
            f"order_api={stage925.get('order_api_called_count', '')}"
        ),
        required="ack suite passed + failed_count=0 + auto_submit_permitted=0 + order_api=0",
        next_action="每次改 Stage924/账户恢复确认格式后复跑 Stage925 和 Stage912。",
    )
    _row(
        rows,
        requirement_id="real_submit_arming_gate",
        requirement="真实提交开关必须由最终机器闸门聚合验收、对账、事故、恢复、调度、心跳和静态边界证据",
        status=(
            "passed"
            if stage927.get("arming_status")
            in {
                "real_submit_arming_blocked_fail_closed",
                "real_submit_arming_ready_requires_explicit_enable",
                "real_submit_arming_permitted_ready",
            }
            and _to_int(stage927.get("order_api_called_count"), -1) == 0
            else "blocked"
            if stage927
            else "missing"
        ),
        evidence=str(stage927_path),
        observed=(
            f"stage927={stage927.get('arming_status', '')};"
            f"real_submit={stage927.get('real_submit_permitted', '')};"
            f"blockers={stage927.get('blocking_failure_count', '')};"
            f"env={stage927.get('env_real_submit_enabled', '')};"
            f"order_api={stage927.get('order_api_called_count', '')}"
        ),
        required="known arming status + order_api=0; unresolved blockers must keep real_submit_permitted=0",
        next_action="Stage913 通过且 broker/shadow aligned 后，再复跑 Stage927；缺确认文本或 env 时仍不得真实提交。",
    )
    _row(
        rows,
        requirement_id="kill_switch",
        requirement="kill switch 可管理、可被控制器和 health check 检出",
        status=(
            "passed"
            if stage912.get("suite_status") == "phase_d_acceptance_passed_fail_closed"
            and bool((stage912_checks.get("check", pd.Series(dtype=str)) == "health_detects_kill_switch").any())
            else "not_proven"
        ),
        evidence=f"{stage912_path}; {stage912_checks_path}",
        observed=f"stage912={stage912.get('suite_status', '')};kill_switch_active_now={_active(kill_switch)}",
        required="Stage912 kill switch checks pass and current kill switch state known",
        next_action="持续纳入上线前验收。",
    )
    _row(
        rows,
        requirement_id="heartbeat",
        requirement="控制器心跳新鲜且 health check 可读",
        status=(
            "passed"
            if stage910.get("health_status") in {"controller_alive_fail_closed", "controller_alive_ready"}
            and _to_int(stage910.get("order_api_called_count"), -1) == 0
            else "blocked"
        ),
        evidence=f"{CONTROLLER_HEARTBEAT_PATH}; {stage910_path}",
        observed=f"stage910={stage910.get('health_status', '')};controller={stage910.get('controller_status', '')};age={stage910.get('heartbeat_age_seconds', '')}",
        required="health status alive and heartbeat age within limit",
        next_action="上线后由 launchd/monitor 周期运行 Stage910。",
    )
    _row(
        rows,
        requirement_id="fail_closed",
        requirement="确认前不能触达真实订单 API",
        status=(
            "passed"
            if stage912.get("suite_status") == "phase_d_acceptance_passed_fail_closed"
            and _to_int(stage912.get("order_api_called_count"), -1) == 0
            else "blocked"
        ),
        evidence=str(stage912_path),
        observed=f"stage912={stage912.get('suite_status', '')};order_api={stage912.get('order_api_called_count', '')}",
        required="Stage912 passed and order_api_called_count=0",
        next_action="每次改动后复跑 Stage912。",
    )

    requirements = pd.DataFrame(rows).sort_values("status", key=lambda s: s.map(_status_rank)).reset_index(drop=True)
    passed_count = int(requirements["status"].eq("passed").sum())
    partial_count = int(requirements["status"].eq("partial").sum())
    incomplete_count = int(requirements["status"].isin(["blocked", "missing", "failed", "not_proven"]).sum())
    order_api_called = max(
        _to_int(stage903.get("order_api_called_count"), 0),
        _to_int(stage912.get("order_api_called_count"), 0),
        _to_int(stage910.get("order_api_called_count"), 0),
        _to_int(stage914.get("order_api_called_count"), 0),
        _to_int(stage915.get("order_api_called_count"), 0),
        _to_int(stage916.get("order_api_called_count"), 0),
        _to_int(stage919.get("order_api_called_count"), 0),
        _to_int(stage920.get("order_api_called_count"), 0),
        _to_int(stage921.get("order_api_called_count"), 0),
        _to_int(stage922.get("order_api_called_count"), 0),
        _to_int(stage923.get("order_api_called_count"), 0),
        _to_int(stage924.get("order_api_called_count"), 0),
        _to_int(stage925.get("order_api_called_count"), 0),
        _to_int(stage926.get("order_api_called_count"), 0),
        _to_int(stage927.get("order_api_called_count"), 0),
    )
    completion_status = (
        "phase_d_completion_proven"
        if incomplete_count == 0 and partial_count == 0 and order_api_called == 0
        else "phase_d_completion_not_proven"
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "completion_status": completion_status,
        "passed_count": passed_count,
        "partial_count": partial_count,
        "incomplete_count": incomplete_count,
        "order_api_called_count": int(order_api_called),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {
            "stage903": str(stage903_path) if stage903_path else "",
            "stage909": str(stage909_path) if stage909_path else "",
            "stage260": str(stage260_path) if stage260_path else "",
            "stage902": str(stage902_path) if stage902_path else "",
            "stage904": str(stage904_path) if stage904_path else "",
            "stage905": str(stage905_path) if stage905_path else "",
            "stage906": str(stage906_path) if stage906_path else "",
            "stage908": str(stage908_path) if stage908_path else "",
            "stage910": str(stage910_path) if stage910_path else "",
            "stage912": str(stage912_path) if stage912_path else "",
            "stage914": str(stage914_path) if stage914_path else "",
            "stage915": str(stage915_path) if stage915_path else "",
            "stage916": str(stage916_path) if stage916_path else "",
            "stage917": str(stage917_path) if stage917_path else "",
            "stage918": str(stage918_path) if stage918_path else "",
            "stage919": str(stage919_path) if stage919_path else "",
            "stage920": str(stage920_path) if stage920_path else "",
            "stage921": str(stage921_path) if stage921_path else "",
            "stage922": str(stage922_path) if stage922_path else "",
            "stage923": str(stage923_path) if stage923_path else "",
            "stage924": str(stage924_path) if stage924_path else "",
            "stage925": str(stage925_path) if stage925_path else "",
            "stage926": str(stage926_path) if stage926_path else "",
            "stage927": str(stage927_path) if stage927_path else "",
        },
        "judgement": {
            "overfit_before": "否。Stage913 是完成度审计，不改策略参数。",
            "continue_before": "是。目标完成必须逐项证据化。",
            "overfit_after": "否。审计结果不反馈策略。",
            "continue_after": "是。当前仍需 fresh broker/tick 和真实 adapter 审查。",
        },
    }
    requirements.to_csv(paths["requirements_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, requirements), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
