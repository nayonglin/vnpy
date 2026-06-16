from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import KILL_SWITCH_PATH
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
MODEL_TAG = "stage912_official_live_phase_d_acceptance_suite_v1"
OUTPUT_PREFIX = "qmt_roll_stage912_official_live_phase_d_acceptance_suite"
STAGE903_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage903_official_live_phase_d_controller.py"
STAGE910_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage910_official_live_phase_d_health_check.py"
STAGE911_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage911_official_live_kill_switch_manager.py"
STAGE915_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage915_official_live_submit_adapter_boundary_suite.py"
STAGE916_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage916_official_live_order_boundary_static_audit.py"
STAGE923_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage923_official_live_fail_closed_incident.py"
STAGE924_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage924_official_live_account_recovery_gate.py"
STAGE925_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage925_official_live_account_recovery_ack_suite.py"
STAGE926_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage926_official_live_aligned_idle_integration.py"
STAGE927_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage927_official_live_real_submit_arming_gate.py"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "commands_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_commands_{run_id}_{MODEL_TAG}.json",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {"_read_error": "json_payload_not_found"}
    try:
        return json.loads(text[start : end + 1])
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _run(name: str, cmd: list[str], timeout_seconds: int = 90) -> dict[str, Any]:
    started = datetime.now()
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_seconds,
        check=False,
    )
    finished = datetime.now()
    return {
        "name": name,
        "command": cmd,
        "exit_code": result.returncode,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "stdout_tail": result.stdout[-5000:],
        "summary": _parse_json_stdout(result.stdout),
    }


def _active(payload: dict[str, Any]) -> bool:
    return bool(payload.get("enabled", False) or payload.get("kill_switch_active", False))


def _to_int(value: Any, default: int = -1) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _restore_kill_switch(original_bytes: bytes | None) -> None:
    if original_bytes is None:
        if KILL_SWITCH_PATH.exists():
            KILL_SWITCH_PATH.unlink()
    else:
        KILL_SWITCH_PATH.parent.mkdir(parents=True, exist_ok=True)
        KILL_SWITCH_PATH.write_bytes(original_bytes)


def _check(rows: list[dict[str, Any]], name: str, passed: bool, observed: Any, required: Any, severity: str = "block") -> None:
    rows.append(
        {
            "check": name,
            "passed": int(bool(passed)),
            "severity": severity,
            "observed": observed,
            "required": required,
            "blocker": "" if passed else name,
        }
    )


def _controller_cmd(target_date: str, mode: str, readonly_refresh_mode: str = "plan-only") -> list[str]:
    return [
        sys.executable,
        str(STAGE903_SCRIPT),
        "--target-date",
        target_date,
        "--mode",
        mode,
        "--shadow-refresh-mode",
        "plan-only",
        "--readonly-refresh-mode",
        readonly_refresh_mode,
        "--stage251-mode",
        "skip",
    ]


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    failed = checks[checks["passed"].eq(0)]
    failed_md = failed.to_markdown(index=False) if not failed.empty else "_empty_"
    checks_md = checks.to_markdown(index=False) if not checks.empty else "_empty_"
    return "\n".join(
        [
            "# Stage912 Official Live Phase D Acceptance Suite",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- suite 状态：`{summary['suite_status']}`",
            f"- 通过数：`{summary['passed_count']}`",
            f"- 失败数：`{summary['failed_count']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Failed Checks",
            "",
            failed_md,
            "",
            "## All Checks",
            "",
            checks_md,
            "",
            "## 说明",
            "",
            "- Stage912 只运行本地 fail-closed 验收，不连接 CTP，不提交委托。",
            "- 套件会临时启用 Phase D kill switch，并在结束时恢复原文件状态。",
            "- 套件同时覆盖 Stage915 adapter boundary 与 Stage916 静态 order boundary。",
            "- 验收通过不代表可以实盘全自动；它只证明当前 fail-closed 防线可回归。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D fail-closed acceptance suite.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    original_bytes = KILL_SWITCH_PATH.read_bytes() if KILL_SWITCH_PATH.exists() else None
    original_payload = _read_json(KILL_SWITCH_PATH)
    original_active = _active(original_payload)
    commands: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    try:
        dry = _run("stage903_dry_run_fail_closed", _controller_cmd(args.target_date, "dry-run"))
        commands.append(dry)
        dry_summary = dry.get("summary", {})
        _check(checks, "dry_run_exit_zero", dry["exit_code"] == 0, dry["exit_code"], 0)
        _check(
            checks,
            "dry_run_controller_fail_closed_or_ready",
            dry_summary.get("controller_status")
            in {
                "phase_d_controller_dry_run_blocked",
                "phase_d_controller_dry_run_ready_real_disabled",
            },
            dry_summary.get("controller_status"),
            "dry-run blocked or ready with real submit still disabled",
        )
        _check(checks, "dry_run_order_api_zero", _to_int(dry_summary.get("order_api_called_count")) == 0, dry_summary.get("order_api_called_count"), 0)
        _check(checks, "dry_run_shadow_plan_only", _to_int(dry_summary.get("stage909_refresh_attempted")) == 0, dry_summary.get("stage909_refresh_attempted"), 0)
        _check(
            checks,
            "dry_run_stage914_preflight_passed",
            dry_summary.get("stage914_preflight_status") == "production_readonly_preflight_passed",
            dry_summary.get("stage914_preflight_status"),
            "production_readonly_preflight_passed",
        )
        _check(checks, "dry_run_stage914_order_api_zero", _to_int(dry_summary.get("stage914_order_api_called_count")) == 0, dry_summary.get("stage914_order_api_called_count"), 0)
        _check(checks, "dry_run_readonly_plan_only", _to_int(dry_summary.get("stage907_refresh_attempted")) == 0, dry_summary.get("stage907_refresh_attempted"), 0)

        refresh_block = _run(
            "stage903_refresh_without_confirmation_fail_closed",
            _controller_cmd(args.target_date, "dry-run", readonly_refresh_mode="refresh"),
        )
        commands.append(refresh_block)
        refresh_summary = refresh_block.get("summary", {})
        _check(checks, "refresh_without_confirm_exit_zero", refresh_block["exit_code"] == 0, refresh_block["exit_code"], 0)
        _check(
            checks,
            "refresh_without_confirm_preflight_passed",
            refresh_summary.get("stage914_preflight_status") == "production_readonly_preflight_passed",
            refresh_summary.get("stage914_preflight_status"),
            "production_readonly_preflight_passed",
        )
        _check(
            checks,
            "refresh_without_confirm_stage907_blocked",
            refresh_summary.get("stage907_refresh_status") == "readonly_refresh_blocked",
            refresh_summary.get("stage907_refresh_status"),
            "readonly_refresh_blocked",
        )
        _check(checks, "refresh_without_confirm_attempt_zero", _to_int(refresh_summary.get("stage907_refresh_attempted")) == 0, refresh_summary.get("stage907_refresh_attempted"), 0)
        _check(checks, "refresh_without_confirm_order_api_zero", _to_int(refresh_summary.get("order_api_called_count")) == 0, refresh_summary.get("order_api_called_count"), 0)

        adapter_boundary = _run(
            "stage915_submit_adapter_boundary_suite",
            [sys.executable, str(STAGE915_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(adapter_boundary)
        adapter_boundary_summary = adapter_boundary.get("summary", {})
        _check(checks, "adapter_boundary_exit_zero", adapter_boundary["exit_code"] == 0, adapter_boundary["exit_code"], 0)
        _check(
            checks,
            "adapter_boundary_passed",
            adapter_boundary_summary.get("adapter_boundary_status") == "phase_d_submit_adapter_boundary_passed",
            adapter_boundary_summary.get("adapter_boundary_status"),
            "phase_d_submit_adapter_boundary_passed",
        )
        _check(checks, "adapter_boundary_real_order_api_zero", _to_int(adapter_boundary_summary.get("real_broker_order_api_called_count")) == 0, adapter_boundary_summary.get("real_broker_order_api_called_count"), 0)

        fail_closed_incident = _run(
            "stage923_fail_closed_incident",
            [sys.executable, str(STAGE923_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(fail_closed_incident)
        fail_closed_incident_summary = fail_closed_incident.get("summary", {})
        _check(checks, "fail_closed_incident_exit_zero", fail_closed_incident["exit_code"] == 0, fail_closed_incident["exit_code"], 0)
        _check(
            checks,
            "fail_closed_incident_status_known",
            fail_closed_incident_summary.get("incident_status")
            in {
                "phase_d_fail_closed_operator_attention_required",
                "phase_d_no_incident_monitor_only",
                "phase_d_no_incident_completion_proven",
            },
            fail_closed_incident_summary.get("incident_status"),
            "known fail-closed incident status",
        )
        _check(checks, "fail_closed_incident_auto_submit_zero", _to_int(fail_closed_incident_summary.get("auto_submit_permitted")) == 0, fail_closed_incident_summary.get("auto_submit_permitted"), 0)
        _check(checks, "fail_closed_incident_order_api_zero", _to_int(fail_closed_incident_summary.get("order_api_called_count")) == 0, fail_closed_incident_summary.get("order_api_called_count"), 0)

        account_recovery_gate = _run(
            "stage924_account_recovery_gate",
            [sys.executable, str(STAGE924_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(account_recovery_gate)
        account_recovery_summary = account_recovery_gate.get("summary", {})
        _check(checks, "account_recovery_gate_exit_zero", account_recovery_gate["exit_code"] == 0, account_recovery_gate["exit_code"], 0)
        _check(
            checks,
            "account_recovery_gate_status_known",
            account_recovery_summary.get("recovery_status")
            in {
                "account_recovery_ack_required_fail_closed",
                "account_recovery_manual_keep_fail_closed",
                "account_recovery_manual_action_pending_fail_closed",
                "account_recovery_manual_action_done_rerun_required",
                "account_recovery_non_strategy_position_ack_recorded_fail_closed",
                "account_recovery_not_required_aligned",
            },
            account_recovery_summary.get("recovery_status"),
            "known account recovery status",
        )
        _check(checks, "account_recovery_gate_auto_submit_zero", _to_int(account_recovery_summary.get("auto_submit_permitted")) == 0, account_recovery_summary.get("auto_submit_permitted"), 0)
        _check(checks, "account_recovery_gate_order_api_zero", _to_int(account_recovery_summary.get("order_api_called_count")) == 0, account_recovery_summary.get("order_api_called_count"), 0)

        account_recovery_ack_suite = _run(
            "stage925_account_recovery_ack_suite",
            [sys.executable, str(STAGE925_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(account_recovery_ack_suite)
        account_recovery_ack_summary = account_recovery_ack_suite.get("summary", {})
        _check(checks, "account_recovery_ack_suite_exit_zero", account_recovery_ack_suite["exit_code"] == 0, account_recovery_ack_suite["exit_code"], 0)
        _check(
            checks,
            "account_recovery_ack_suite_passed",
            account_recovery_ack_summary.get("suite_status") == "account_recovery_ack_suite_passed_fail_closed",
            account_recovery_ack_summary.get("suite_status"),
            "account_recovery_ack_suite_passed_fail_closed",
        )
        _check(checks, "account_recovery_ack_suite_failed_zero", _to_int(account_recovery_ack_summary.get("failed_count")) == 0, account_recovery_ack_summary.get("failed_count"), 0)
        _check(checks, "account_recovery_ack_suite_auto_submit_zero", _to_int(account_recovery_ack_summary.get("auto_submit_permitted")) == 0, account_recovery_ack_summary.get("auto_submit_permitted"), 0)
        _check(checks, "account_recovery_ack_suite_order_api_zero", _to_int(account_recovery_ack_summary.get("order_api_called_count")) == 0, account_recovery_ack_summary.get("order_api_called_count"), 0)

        aligned_idle = _run(
            "stage926_aligned_idle_integration",
            [sys.executable, str(STAGE926_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(aligned_idle)
        aligned_idle_summary = aligned_idle.get("summary", {})
        _check(checks, "aligned_idle_integration_exit_zero", aligned_idle["exit_code"] == 0, aligned_idle["exit_code"], 0)
        _check(
            checks,
            "aligned_idle_integration_passed",
            aligned_idle_summary.get("idle_integration_status") == "aligned_idle_no_action_passed_fail_closed",
            aligned_idle_summary.get("idle_integration_status"),
            "aligned_idle_no_action_passed_fail_closed",
        )
        _check(checks, "aligned_idle_integration_restored", _to_int(aligned_idle_summary.get("real_snapshot_restored")) == 1, aligned_idle_summary.get("real_snapshot_restored"), 1)
        _check(checks, "aligned_idle_integration_order_api_zero", _to_int(aligned_idle_summary.get("order_api_called_count")) == 0, aligned_idle_summary.get("order_api_called_count"), 0)

        real_submit_arming = _run(
            "stage927_real_submit_arming_gate",
            [sys.executable, str(STAGE927_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(real_submit_arming)
        real_submit_arming_summary = real_submit_arming.get("summary", {})
        _check(checks, "real_submit_arming_exit_zero", real_submit_arming["exit_code"] == 0, real_submit_arming["exit_code"], 0)
        _check(
            checks,
            "real_submit_arming_status_known",
            real_submit_arming_summary.get("arming_status")
            in {
                "real_submit_arming_blocked_fail_closed",
                "real_submit_arming_ready_requires_explicit_enable",
                "real_submit_arming_permitted_ready",
            },
            real_submit_arming_summary.get("arming_status"),
            "known real-submit arming status",
        )
        _check(checks, "real_submit_arming_permitted_zero", _to_int(real_submit_arming_summary.get("real_submit_permitted")) == 0, real_submit_arming_summary.get("real_submit_permitted"), 0)
        _check(checks, "real_submit_arming_order_api_zero", _to_int(real_submit_arming_summary.get("order_api_called_count")) == 0, real_submit_arming_summary.get("order_api_called_count"), 0)

        static_boundary = _run(
            "stage916_order_boundary_static_audit",
            [sys.executable, str(STAGE916_SCRIPT), "--target-date", args.target_date],
        )
        commands.append(static_boundary)
        static_boundary_summary = static_boundary.get("summary", {})
        _check(checks, "static_boundary_exit_zero", static_boundary["exit_code"] == 0, static_boundary["exit_code"], 0)
        _check(
            checks,
            "static_boundary_passed",
            static_boundary_summary.get("static_audit_status") == "phase_d_order_boundary_static_audit_passed",
            static_boundary_summary.get("static_audit_status"),
            "phase_d_order_boundary_static_audit_passed",
        )
        _check(checks, "static_boundary_disallowed_zero", _to_int(static_boundary_summary.get("disallowed_reference_count")) == 0, static_boundary_summary.get("disallowed_reference_count"), 0)

        live = _run("stage903_live_real_without_confirmation_fail_closed", _controller_cmd(args.target_date, "live-real"))
        commands.append(live)
        live_summary = live.get("summary", {})
        _check(checks, "live_real_exit_zero", live["exit_code"] == 0, live["exit_code"], 0)
        _check(
            checks,
            "live_real_controller_without_confirmation_not_submitted",
            live_summary.get("controller_status")
            in {
                "phase_d_controller_live_real_blocked",
                "phase_d_controller_live_real_ready_no_submit_step",
            },
            live_summary.get("controller_status"),
            "live-real blocked or ready_no_submit_step without confirmation",
        )
        _check(checks, "live_real_submit_permitted_zero", _to_int(live_summary.get("stage908_live_submit_permitted")) == 0, live_summary.get("stage908_live_submit_permitted"), 0)
        _check(checks, "live_real_order_api_zero", _to_int(live_summary.get("order_api_called_count")) == 0, live_summary.get("order_api_called_count"), 0)

        kill_enable = _run(
            "stage911_enable_kill_switch",
            [
                sys.executable,
                str(STAGE911_SCRIPT),
                "--action",
                "enable",
                "--reason",
                f"stage912_acceptance_suite_{run_id}",
                "--actor",
                "stage912",
            ],
        )
        commands.append(kill_enable)
        kill_enable_summary = kill_enable.get("summary", {})
        _check(checks, "kill_enable_exit_zero", kill_enable["exit_code"] == 0, kill_enable["exit_code"], 0)
        _check(checks, "kill_switch_enabled", bool(kill_enable_summary.get("kill_switch_active_after")), kill_enable_summary.get("kill_switch_active_after"), True)

        killed = _run("stage903_kill_switch_fail_closed", _controller_cmd(args.target_date, "dry-run"))
        commands.append(killed)
        killed_summary = killed.get("summary", {})
        _check(checks, "killed_controller_exit_zero", killed["exit_code"] == 0, killed["exit_code"], 0)
        _check(
            checks,
            "killed_controller_status",
            killed_summary.get("controller_status") == "phase_d_controller_killed",
            killed_summary.get("controller_status"),
            "phase_d_controller_killed",
        )
        _check(checks, "killed_order_api_zero", _to_int(killed_summary.get("order_api_called_count")) == 0, killed_summary.get("order_api_called_count"), 0)

        health_killed = _run(
            "stage910_health_detects_kill_switch",
            [sys.executable, str(STAGE910_SCRIPT), "--max-heartbeat-age-seconds", "300"],
        )
        commands.append(health_killed)
        health_killed_summary = health_killed.get("summary", {})
        _check(checks, "health_killed_exit_zero", health_killed["exit_code"] == 0, health_killed["exit_code"], 0)
        _check(
            checks,
            "health_detects_kill_switch",
            bool(health_killed_summary.get("kill_switch_active")) and health_killed_summary.get("health_status") == "controller_health_blocked",
            f"active={health_killed_summary.get('kill_switch_active')};status={health_killed_summary.get('health_status')}",
            "active=True;status=controller_health_blocked",
        )
    finally:
        _restore_kill_switch(original_bytes)

    restored_payload = _read_json(KILL_SWITCH_PATH)
    restored_active = _active(restored_payload)
    _check(
        checks,
        "kill_switch_restored",
        restored_active == original_active,
        f"before={original_active};after={restored_active}",
        "restored to original active state",
    )
    checks_df = pd.DataFrame(checks)
    failed = checks_df[checks_df["passed"].eq(0)]
    order_api_called = sum(int(command.get("summary", {}).get("order_api_called_count", 0) or 0) for command in commands)
    suite_status = "phase_d_acceptance_passed_fail_closed" if failed.empty and order_api_called == 0 else "phase_d_acceptance_failed"
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "suite_status": suite_status,
        "passed_count": int(checks_df["passed"].sum()) if not checks_df.empty else 0,
        "failed_count": int(len(failed)),
        "order_api_called_count": int(order_api_called),
        "kill_switch_original_active": original_active,
        "kill_switch_restored_active": restored_active,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。验收套件只测试执行安全状态，不改策略参数。",
            "continue_before": "是。全自动上线前必须有可重复 fail-closed 回归。",
            "overfit_after": "否。结果只证明控制面行为。",
            "continue_after": "是。下一步仍需 fresh broker/tick 证据后再跑通过性验收。",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["commands_json"].write_text(json.dumps(commands, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
