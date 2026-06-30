from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
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


def _production_live_command(wait_seconds: int) -> tuple[list[str], str]:
    env_file = PROJECT_DIR / "ctp_live.local.env"
    framework_dir = REPO_ROOT / ".py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"
    py311_lib = REPO_ROOT / ".py311/lib"
    python_path = REPO_ROOT / ".py311/bin/python"
    probe = PROJECT_DIR / "run_ctp_stage174_readonly_probe.py"
    shell = "\n".join(
        [
            "set -euo pipefail",
            f"set -a; source {shlex.quote(str(env_file))}; set +a",
            (
                "export DYLD_FRAMEWORK_PATH="
                f"{shlex.quote(str(framework_dir))}:{shlex.quote(str(py311_lib))}"
                "${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"
            ),
            f"{shlex.quote(str(python_path))} {shlex.quote(str(probe))} --connect --wait-seconds {int(wait_seconds)}",
        ]
    )
    return ["bash", "-lc", shell], shell


def _wrapper_command(env_profile: str, wait_seconds: int) -> tuple[list[str], str]:
    if env_profile == "simnow":
        wrapper = PROJECT_DIR / "run_ctp_stage177_simnow_readonly_probe.sh"
    elif env_profile == "broker-test":
        wrapper = PROJECT_DIR / "run_ctp_stage267_broker_test_readonly_probe.sh"
    else:
        raise ValueError(f"Unsupported wrapper env profile: {env_profile}")
    cmd = ["bash", str(wrapper), "--connect", "--wait-seconds", str(int(wait_seconds))]
    return cmd, " ".join(shlex.quote(part) for part in cmd)


def _command_for_profile(env_profile: str, wait_seconds: int) -> tuple[list[str], str]:
    if env_profile == "production-live":
        return _production_live_command(wait_seconds)
    return _wrapper_command(env_profile, wait_seconds)


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
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    cmd, command_plan = _command_for_profile(args.env_profile, args.wait_seconds)
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
    broker_snapshot = readonly_summary.get("broker_snapshot", {}) if isinstance(readonly_summary.get("broker_snapshot"), dict) else {}
    position_state = str(broker_snapshot.get("position_snapshot_state", ""))
    readonly_ready = readonly_summary.get("status") == "readonly_snapshots_received" and position_state in {
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
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        "env_profile": args.env_profile,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "refresh_status": refresh_status,
        "refresh_attempted": int(refresh_attempted),
        "readonly_status_after": readonly_summary.get("status", ""),
        "position_snapshot_state_after": position_state,
        "command_exit_code": command_result.get("exit_code", ""),
        "blocking_failure_count": int(len(blocking)),
        "order_api_called_count": 0,
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
