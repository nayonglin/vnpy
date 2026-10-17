from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_ENV,
    READONLY_SUMMARY_PATH,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
MODEL_TAG = "stage907_official_live_readonly_refresh_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage907_official_live_readonly_refresh_gate"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "command_log": OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_log_{run_id}_{MODEL_TAG}.txt",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 else ""


def _readonly_order_api_evidence(summary: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "send_order_api_attempted_count",
        "cancel_order_api_attempted_count",
        "send_order_api_called_count",
        "cancel_order_api_called_count",
        "native_mutation_api_attempted_count",
        "native_mutation_api_called_count",
        "order_api_attempted_count",
        "order_api_called_count",
    )
    missing = [
        field
        for field in fields
        if type(summary.get(field)) is not int
        or int(summary[field]) < 0
    ]
    nonzero = [
        field
        for field in fields
        if field not in missing and int(summary[field]) != 0
    ]
    return {
        "complete": not missing and not nonzero,
        "missing_fields": missing,
        "nonzero_fields": nonzero,
        **{
            field: summary.get(field) if field not in missing else None
            for field in fields
        },
    }


def _datetime_epoch(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.timestamp()


def _readonly_snapshot_evidence(
    summary: dict[str, Any],
    *,
    previous_generation: str,
    command_started_at: str,
    refresh_attempted: bool,
    expected_invocation_id: str,
    command_stdout_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    missing: list[str] = []
    generation = str(summary.get("query_generation_uuid") or "").strip()
    bundle = summary.get("broker_query_bundle")
    if not isinstance(bundle, dict):
        bundle = {}
        missing.append("broker_query_bundle")
    if bundle.get("complete") is not True:
        missing.append("broker_query_bundle.complete")
    if not generation:
        missing.append("query_generation_uuid")
    if str(bundle.get("generation_uuid") or "").strip() != generation:
        missing.append("broker_query_bundle.generation_uuid")
    if refresh_attempted and previous_generation and generation == previous_generation:
        missing.append("query_generation_uuid_not_new")
    generated_epoch = _datetime_epoch(summary.get("generated_at"))
    command_epoch = _datetime_epoch(command_started_at)
    if refresh_attempted and (
        generated_epoch is None
        or command_epoch is None
        or generated_epoch < command_epoch
    ):
        missing.append("summary_generated_before_command_start")
    if not refresh_attempted:
        missing.append("refresh_not_attempted")
    invocation_id = str(summary.get("invocation_id") or "").strip()
    if not expected_invocation_id or invocation_id != expected_invocation_id:
        missing.append("invocation_id_mismatch")
    stdout_summary = (
        command_stdout_summary if isinstance(command_stdout_summary, dict) else {}
    )
    file_summary_sha256 = _canonical_json_sha256(summary)
    stdout_summary_sha256 = (
        _canonical_json_sha256(stdout_summary) if stdout_summary else ""
    )
    stdout_file_payload_match = bool(
        stdout_summary_sha256 and stdout_summary_sha256 == file_summary_sha256
    )
    if refresh_attempted:
        if not stdout_summary:
            missing.append("stage174_stdout_summary_missing")
        elif not stdout_file_payload_match:
            missing.append("stage174_stdout_file_payload_mismatch")
    return {
        "complete": not missing,
        "missing_fields": missing,
        "generation_uuid": generation,
        "bundle_complete": bundle.get("complete"),
        "generated_epoch": generated_epoch,
        "command_started_epoch": command_epoch,
        "invocation_id": invocation_id,
        "expected_invocation_id": expected_invocation_id,
        "file_summary_sha256": file_summary_sha256,
        "stdout_summary_sha256": stdout_summary_sha256,
        "stdout_file_payload_match": int(stdout_file_payload_match),
    }


def _canonical_json_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _extract_stage174_stdout_summary(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        return {}
    try:
        payload, _ = json.JSONDecoder().raw_decode(stdout[start:])
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _check_row(
    rows: list[dict[str, Any]],
    *,
    check: str,
    passed: bool,
    severity: str,
    observed: Any,
    required: Any,
    blocker: str = "",
) -> None:
    rows.append(
        {
            "check": check,
            "passed": int(bool(passed)),
            "severity": severity,
            "observed": observed,
            "required": required,
            "blocker": "" if passed else blocker,
        }
    )


def _production_live_command(
    wait_seconds: int,
    invocation_id: str,
    observe_reconnect: bool = False,
) -> tuple[list[str], str]:
    env_file = PROJECT_DIR / "ctp_live.local.env"
    framework_dir = REPO_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
    py311_lib = REPO_ROOT / ".py311/lib"
    python_path = REPO_ROOT / ".py311/bin/python"
    probe = PROJECT_DIR / "run_ctp_stage174_readonly_probe.py"
    reconnect_arg = " --observe-reconnect" if observe_reconnect else ""
    shell = "\n".join(
        [
            "set -euo pipefail",
            f"set -a; source {shlex.quote(str(env_file))}; set +a",
            (
                "export DYLD_FRAMEWORK_PATH="
                f"{shlex.quote(str(framework_dir))}:{shlex.quote(str(py311_lib))}"
                "${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"
            ),
            (
                f"{shlex.quote(str(python_path))} {shlex.quote(str(probe))} "
                f"--connect --wait-seconds {int(wait_seconds)} "
                f"--invocation-id {shlex.quote(invocation_id)}{reconnect_arg}"
            ),
        ]
    )
    return ["bash", "-lc", shell], shell


def _wrapper_command(
    env_profile: str,
    wait_seconds: int,
    invocation_id: str,
    observe_reconnect: bool = False,
) -> tuple[list[str], str]:
    if env_profile == "simnow":
        wrapper = PROJECT_DIR / "run_ctp_stage177_simnow_readonly_probe.sh"
    elif env_profile == "broker-test":
        wrapper = PROJECT_DIR / "run_ctp_stage267_broker_test_readonly_probe.sh"
    else:
        raise ValueError(f"Unsupported wrapper env profile: {env_profile}")
    cmd = [
        "bash",
        str(wrapper),
        "--connect",
        "--wait-seconds",
        str(int(wait_seconds)),
        "--invocation-id",
        invocation_id,
    ]
    if observe_reconnect:
        cmd.append("--observe-reconnect")
    return cmd, " ".join(shlex.quote(part) for part in cmd)


def _command_for_profile(
    env_profile: str,
    wait_seconds: int,
    invocation_id: str,
    observe_reconnect: bool = False,
) -> tuple[list[str], str]:
    if env_profile == "production-live":
        return _production_live_command(
            wait_seconds, invocation_id, observe_reconnect
        )
    return _wrapper_command(
        env_profile, wait_seconds, invocation_id, observe_reconnect
    )


def _profile_checks(rows: list[dict[str, Any]], env_profile: str) -> None:
    if env_profile == "production-live":
        env_file = PROJECT_DIR / "ctp_live.local.env"
        framework_dir = REPO_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
        _check_row(
            rows,
            check="production_live_env_file_present",
            passed=env_file.exists(),
            severity="block",
            observed=str(env_file),
            required="ctp_live.local.env exists",
            blocker="ctp_live_env_file_missing",
        )
        _check_row(
            rows,
            check="production_live_framework_priority_path_present",
            passed=framework_dir.exists(),
            severity="block",
            observed=str(framework_dir),
            required="vnpy_ctp/api/libs formal framework path exists",
            blocker="formal_vnpy_ctp_framework_path_missing",
        )
    elif env_profile in {"simnow", "broker-test"}:
        wrapper = PROJECT_DIR / (
            "run_ctp_stage177_simnow_readonly_probe.sh"
            if env_profile == "simnow"
            else "run_ctp_stage267_broker_test_readonly_probe.sh"
        )
        _check_row(
            rows,
            check=f"{env_profile}_readonly_wrapper_present",
            passed=wrapper.exists(),
            severity="block",
            observed=str(wrapper),
            required="readonly wrapper exists",
            blocker="readonly_wrapper_missing",
        )


def _run_command(cmd: list[str], command_log: Path, timeout_seconds: int) -> dict[str, Any]:
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout_seconds,
    )
    command_log.write_text(result.stdout, encoding="utf-8")
    finished = datetime.now()
    return {
        "exit_code": result.returncode,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "stdout_tail": result.stdout[-4000:],
        "stage174_stdout_summary": _extract_stage174_stdout_summary(result.stdout),
    }


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(80).to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    blocking = checks[checks["severity"].eq("block") & checks["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage907 Official Live Readonly Refresh Gate",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 请求模式：`{summary['mode']}`",
            f"- 环境 profile：`{summary['env_profile']}`",
            f"- refresh 状态：`{summary['refresh_status']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Blocking Checks",
            "",
            _to_markdown(blocking, ["check", "observed", "required", "blocker"]),
            "",
            "## Command Plan",
            "",
            f"```bash\n{summary['sanitized_command_plan']}\n```",
            "",
            "## 说明",
            "",
            "- Stage907 只处理 CTP read-only refresh，不处理提交委托。",
            "- `plan-only` 模式只生成命令和阻断项，不连接 CTP。",
            "- `refresh` 模式必须同时满足 env gate 与确认文本；production-live 强制使用 `ctp_live.local.env` 和正式 `vnpy_ctp/api/libs` framework 优先级。",
            "",
        ]
    )


def _send_email_if_needed(
    *,
    summary: dict[str, Any],
    paths: dict[str, Path],
    policy: str,
) -> dict[str, Any]:
    success = (
        summary.get("refresh_status") == "readonly_refresh_completed_snapshot_ready"
        and int(summary.get("blocking_failure_count", 0)) == 0
    )
    if policy == "never" or (policy == "on-failure" and success):
        return {"email_status": "skipped_by_policy", "email_policy": policy}

    severity = "info" if success else "warning"
    status_text = "成功" if success else "失败/需检查"
    subject = (
        f"[C9/15w][15:05只读快照]{status_text} "
        f"{summary.get('refresh_status', '')} API={summary.get('order_api_called_count', 0)}"
    )
    body = "\n".join(
        [
            f"结论：15:05 只读快照{status_text}。",
            f"时间：{summary.get('generated_at', '')}",
            f"当前官方实盘：{summary.get('official_live_alias', '')}",
            f"刷新状态：{summary.get('refresh_status', '')}",
            f"CTP只读状态：{summary.get('readonly_status_after', '')}",
            f"持仓快照状态：{summary.get('position_snapshot_state_after', '')}",
            f"阻断数：{summary.get('blocking_failure_count', 0)}",
            f"订单API：{summary.get('order_api_called_count', 0)}",
            "说明：这封邮件只确认 15:05 账户/持仓只读快照，不生成交易信号，不提交订单。",
            "下一步：16:35 仍由 post-close 报告邮件给出收盘后信号、对账和今晚计划。",
        ]
    )
    return send_official_live_email_notification(
        subject=subject,
        body=body,
        event_type="stage907_day_close_readonly",
        severity=severity,
        attachments=[paths["report_md"], paths["summary_json"]],
        metadata={
            "mode": summary.get("mode", ""),
            "env_profile": summary.get("env_profile", ""),
            "refresh_status": summary.get("refresh_status", ""),
            "blocking_failure_count": summary.get("blocking_failure_count", 0),
            "order_api_called_count": summary.get("order_api_called_count", 0),
            "email_policy": policy,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live read-only refresh gate.")
    parser.add_argument("--mode", choices=["plan-only", "refresh"], default="plan-only")
    parser.add_argument("--env-profile", choices=["production-live", "simnow", "broker-test"], default="production-live")
    parser.add_argument("--wait-seconds", type=int, default=30)
    parser.add_argument("--confirm-readonly-refresh", default="")
    parser.add_argument("--email-policy", choices=["never", "on-failure", "always"], default="never")
    parser.add_argument("--observe-reconnect", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    invocation_id = uuid.uuid4().hex
    cmd, command_plan = _command_for_profile(
        args.env_profile,
        args.wait_seconds,
        invocation_id,
        bool(args.observe_reconnect),
    )
    checks: list[dict[str, Any]] = []
    _profile_checks(checks, args.env_profile)
    refresh_env_enabled = _env_enabled(PHASE_D_READONLY_REFRESH_ENV)
    confirm_ok = args.confirm_readonly_refresh == PHASE_D_READONLY_REFRESH_CONFIRM_TEXT
    _check_row(
        checks,
        check="readonly_refresh_env_gate_enabled",
        passed=args.mode == "plan-only" or refresh_env_enabled,
        severity="block",
        observed=f"{PHASE_D_READONLY_REFRESH_ENV}={os.getenv(PHASE_D_READONLY_REFRESH_ENV, '')}",
        required=f"{PHASE_D_READONLY_REFRESH_ENV}=1 when --mode refresh",
        blocker="readonly_refresh_env_gate_missing",
    )
    _check_row(
        checks,
        check="readonly_refresh_confirmation",
        passed=args.mode == "plan-only" or confirm_ok,
        severity="block",
        observed=f"mode={args.mode};confirm_ok={confirm_ok}",
        required=PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
        blocker="readonly_refresh_confirmation_missing",
    )

    checks_df = pd.DataFrame(checks)
    blocking = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]
    readonly_summary_before = _read_json(READONLY_SUMMARY_PATH)
    command_result: dict[str, Any] = {}
    refresh_attempted = False
    if args.mode == "refresh" and blocking.empty:
        refresh_attempted = True
        command_result = _run_command(
            cmd,
            paths["command_log"],
            timeout_seconds=max(20, int(args.wait_seconds) + 45),
        )
    else:
        paths["command_log"].write_text("", encoding="utf-8")

    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    order_api_evidence = _readonly_order_api_evidence(readonly_summary)
    snapshot_evidence = _readonly_snapshot_evidence(
        readonly_summary,
        previous_generation=str(
            readonly_summary_before.get("query_generation_uuid") or ""
        ).strip(),
        command_started_at=str(command_result.get("started_at") or ""),
        refresh_attempted=refresh_attempted,
        expected_invocation_id=invocation_id,
        command_stdout_summary=command_result.get("stage174_stdout_summary"),
    )
    _check_row(
        checks,
        check="readonly_order_api_exact_zero_evidence",
        passed=bool(order_api_evidence["complete"]),
        severity="block",
        observed=(
            f"missing={order_api_evidence['missing_fields']};"
            f"nonzero={order_api_evidence['nonzero_fields']}"
        ),
        required="Stage174 gateway and TD API attempted/called counters are exact integer 0/0",
        blocker="readonly_order_api_evidence_incomplete_or_nonzero",
    )
    _check_row(
        checks,
        check="readonly_snapshot_new_complete_bundle",
        passed=bool(snapshot_evidence["complete"]),
        severity="block",
        observed=f"missing={snapshot_evidence['missing_fields']}",
        required="new Stage174 generation after command start with broker_query_bundle.complete=true",
        blocker="readonly_snapshot_stale_or_incomplete",
    )
    checks_df = pd.DataFrame(checks)
    blocking = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]
    broker_snapshot = readonly_summary.get("broker_snapshot", {}) if isinstance(readonly_summary.get("broker_snapshot"), dict) else {}
    position_state = str(broker_snapshot.get("position_snapshot_state", ""))
    readonly_ready = bool(order_api_evidence["complete"]) and bool(snapshot_evidence["complete"]) and readonly_summary.get("status") == "readonly_snapshots_received" and position_state in {
        "confirmed_flat",
        "positions_received",
    }
    if args.mode == "plan-only":
        refresh_status = "readonly_refresh_plan_only"
    elif not blocking.empty:
        refresh_status = "readonly_refresh_blocked"
    elif command_result.get("exit_code") != 0:
        refresh_status = "readonly_refresh_command_failed"
    elif readonly_ready:
        refresh_status = "readonly_refresh_completed_snapshot_ready"
    else:
        refresh_status = "readonly_refresh_attempted_snapshot_not_ready"

    summary = {
        "model_tag": MODEL_TAG,
        "source_commit": _source_commit(),
        "stage174_source_commit": readonly_summary.get("source_commit", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        "env_profile": args.env_profile,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "refresh_status": refresh_status,
        "refresh_attempted": int(refresh_attempted),
        "observe_reconnect": int(bool(args.observe_reconnect)),
        "readonly_status_after": readonly_summary.get("status", ""),
        "position_snapshot_state_after": position_state,
        "command_exit_code": command_result.get("exit_code", ""),
        "blocking_failure_count": int(len(blocking)),
        "send_order_api_attempted_count": order_api_evidence.get("send_order_api_attempted_count"),
        "cancel_order_api_attempted_count": order_api_evidence.get("cancel_order_api_attempted_count"),
        "send_order_api_called_count": order_api_evidence.get("send_order_api_called_count"),
        "cancel_order_api_called_count": order_api_evidence.get("cancel_order_api_called_count"),
        "native_mutation_api_attempted_count": order_api_evidence.get(
            "native_mutation_api_attempted_count"
        ),
        "native_mutation_api_called_count": order_api_evidence.get(
            "native_mutation_api_called_count"
        ),
        "order_api_attempted_count": order_api_evidence.get(
            "order_api_attempted_count"
        ),
        "order_api_called_count": order_api_evidence.get("order_api_called_count"),
        "order_api_evidence_complete": int(bool(order_api_evidence["complete"])),
        "order_api_evidence_missing_fields": order_api_evidence["missing_fields"],
        "order_api_evidence_nonzero_fields": order_api_evidence["nonzero_fields"],
        "snapshot_evidence_complete": int(bool(snapshot_evidence["complete"])),
        "snapshot_evidence_missing_fields": snapshot_evidence["missing_fields"],
        "snapshot_generation_uuid": snapshot_evidence["generation_uuid"],
        "stage174_invocation_id": snapshot_evidence["invocation_id"],
        "stage174_file_summary_sha256": snapshot_evidence[
            "file_summary_sha256"
        ],
        "stage174_stdout_summary_sha256": snapshot_evidence[
            "stdout_summary_sha256"
        ],
        "stage174_stdout_file_payload_match": snapshot_evidence[
            "stdout_file_payload_match"
        ],
        "broker_query_bundle_complete": snapshot_evidence["bundle_complete"],
        "connection_lifecycle": (
            readonly_summary.get("connection_lifecycle")
            if isinstance(readonly_summary.get("connection_lifecycle"), dict)
            else {}
        ),
        "sanitized_command_plan": command_plan,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。只读刷新是执行环境工程，不改策略参数。",
            "continue_before": "是。全自动需要常驻进程能安全刷新 broker 快照。",
            "overfit_after": "否。只读结果只用于执行闸门。",
            "continue_after": "是。下一步应将 plan-only/refresh 状态接入 Stage903，并保持默认不连接。",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    email_result = _send_email_if_needed(summary=summary, paths=paths, policy=str(args.email_policy))
    summary["email_notification"] = email_result
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
