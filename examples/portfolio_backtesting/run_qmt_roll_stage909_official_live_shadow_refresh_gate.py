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

from qmt_roll_official_execution_profile import (
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    resolve_execution_profile,
)
from qmt_roll_official_live_config import OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
    PHASE_D_SHADOW_REFRESH_ENV,
)
from run_qmt_roll_stage922_official_live_target_date_resolver import (
    _resolve_latest_completed,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
MODEL_TAG = "stage909_official_live_shadow_refresh_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage909_official_live_shadow_refresh_gate"
STAGE173_SCRIPT = PROJECT_DIR / "build_qmt_roll_stage173_forward_main_contract_data_update.py"
OFFICIAL_SHADOW_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py"
STAGE372_PENDING_AUDIT_SCRIPT = (
    PROJECT_DIR / "export_qmt_roll_stage372_official_shadow_events.py"
)


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
        "command_log": OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_log_{date_key}_{MODEL_TAG}.txt",
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


def _month_start(target_date: str) -> str:
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        return dt.replace(day=1).date().isoformat()
    except ValueError:
        return target_date


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


def _run_command(name: str, cmd: list[str], log_path: Path) -> dict[str, Any]:
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
        check=False,
    )
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n\n===== {name} | {started:%Y-%m-%d %H:%M:%S} =====\n")
        log.write("$ " + " ".join(cmd) + "\n")
        log.write(result.stdout)
        log.write(f"\nexit_code={result.returncode}\n")
    finished = datetime.now()
    return {
        "name": name,
        "command": cmd,
        "exit_code": result.returncode,
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
    }


def _command_specs(
    target_date: str,
    mapping_start: str,
    bar_start: str,
    analysis_start: str,
    execution_profile: OfficialExecutionProfile,
) -> list[tuple[str, list[str]]]:
    specs = [
        (
            "stage173_data_update",
            [
                str(Path(sys.executable).resolve()),
                str(STAGE173_SCRIPT),
                "--mapping-start",
                mapping_start,
                "--bar-start",
                bar_start,
                "--end",
                target_date,
            ],
        ),
        (
            "official_live_shadow",
            [
                str(Path(sys.executable).resolve()),
                str(OFFICIAL_SHADOW_SCRIPT),
                "--execution-profile",
                execution_profile.profile_key,
                "--analysis-start",
                analysis_start,
                "--target-date",
                target_date,
            ],
        ),
    ]
    if not execution_profile.intraday_stop_retry_enabled:
        specs.append(
            (
                "stage372_pending_order_audit",
                [
                    str(Path(sys.executable).resolve()),
                    str(STAGE372_PENDING_AUDIT_SCRIPT),
                    "--analysis-start",
                    analysis_start,
                    "--target-date",
                    target_date,
                ],
            )
        )
    return specs


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(80).to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    blocking = checks[checks["severity"].eq("block") & checks["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage909 Official Live Shadow Refresh Gate",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- 请求模式：`{summary['mode']}`",
            f"- refresh 状态：`{summary['shadow_refresh_status']}`",
            f"- refresh_attempted：`{summary['refresh_attempted']}`",
            "",
            "## Blocking Checks",
            "",
            _to_markdown(blocking, ["check", "observed", "required", "blocker"]),
            "",
            "## Command Plan",
            "",
            "```bash",
            *summary["sanitized_command_plan"],
            "```",
            "",
            "## 说明",
            "",
            "- Stage909 负责日终数据更新和当前官方 live shadow 计算。",
            "- 默认 `plan-only` 不运行数据更新，不改写 shadow 输出。",
            "- `run` 模式必须同时满足 env gate 与确认文本。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live shadow refresh gate.")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.STAGE372_20W.value,
    )
    parser.add_argument("--target-date", default="")
    parser.add_argument(
        "--target-date-mode",
        choices=["explicit", "latest-completed"],
        default="explicit",
    )
    parser.add_argument("--target-date-data-ready-time", default="16:30")
    parser.add_argument("--mode", choices=["plan-only", "run"], default="plan-only")
    parser.add_argument("--analysis-start", default="")
    parser.add_argument("--mapping-start", default="")
    parser.add_argument("--bar-start", default="")
    parser.add_argument("--confirm-shadow-refresh", default="")
    args = parser.parse_args()
    profile = resolve_execution_profile(args.execution_profile)
    if args.target_date_mode == "latest-completed":
        target_date, target_date_evidence = _resolve_latest_completed(
            datetime.now(),
            args.target_date_data_ready_time,
        )
    else:
        target_date = str(args.target_date).strip()
        target_date_evidence = {"source": "explicit"}
    if not target_date:
        parser.error("--target-date is required in explicit mode")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(target_date)
    paths["command_log"].write_text("", encoding="utf-8")
    mapping_start = args.mapping_start or _month_start(target_date)
    bar_start = args.bar_start or target_date
    analysis_start = args.analysis_start or (
        "2026-01-01"
        if profile.profile_key == ExecutionStrategyMode.STAGE372_20W.value
        else OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
    )
    specs = _command_specs(
        target_date,
        mapping_start,
        bar_start,
        analysis_start,
        profile,
    )
    command_plan = [" ".join(cmd) for _, cmd in specs]
    refresh_env_enabled = _env_enabled(PHASE_D_SHADOW_REFRESH_ENV)
    confirm_ok = args.confirm_shadow_refresh == PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT

    checks: list[dict[str, Any]] = []
    _check_row(
        checks,
        check="stage173_script_present",
        passed=STAGE173_SCRIPT.exists(),
        severity="block",
        observed=str(STAGE173_SCRIPT),
        required="data update script exists",
        blocker="stage173_script_missing",
    )
    _check_row(
        checks,
        check="official_shadow_script_present",
        passed=OFFICIAL_SHADOW_SCRIPT.exists(),
        severity="block",
        observed=str(OFFICIAL_SHADOW_SCRIPT),
        required="official shadow script exists",
        blocker="official_shadow_script_missing",
    )
    if not profile.intraday_stop_retry_enabled:
        _check_row(
            checks,
            check="stage372_pending_audit_script_present",
            passed=STAGE372_PENDING_AUDIT_SCRIPT.exists(),
            severity="block",
            observed=str(STAGE372_PENDING_AUDIT_SCRIPT),
            required="Stage372 pending-order audit script exists",
            blocker="stage372_pending_audit_script_missing",
        )
    _check_row(
        checks,
        check="shadow_refresh_env_gate_enabled",
        passed=args.mode == "plan-only" or refresh_env_enabled,
        severity="block",
        observed=f"{PHASE_D_SHADOW_REFRESH_ENV}={os.getenv(PHASE_D_SHADOW_REFRESH_ENV, '')}",
        required=f"{PHASE_D_SHADOW_REFRESH_ENV}=1 when --mode run",
        blocker="shadow_refresh_env_gate_missing",
    )
    _check_row(
        checks,
        check="shadow_refresh_confirmation",
        passed=args.mode == "plan-only" or confirm_ok,
        severity="block",
        observed=f"mode={args.mode};confirm_ok={confirm_ok}",
        required=PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        blocker="shadow_refresh_confirmation_missing",
    )
    checks_df = pd.DataFrame(checks)
    blocking = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]

    commands: list[dict[str, Any]] = []
    refresh_attempted = False
    if args.mode == "run" and blocking.empty:
        refresh_attempted = True
        for name, cmd in specs:
            row = _run_command(name, cmd, paths["command_log"])
            commands.append(row)
            if row["exit_code"] != 0:
                break

    official_summary = _read_json(profile.summary_path)
    shadow_target_ready = str(official_summary.get("analysis_end", "")) == target_date
    pending_audit_summary = _read_json(
        OUTPUT_DIR
        / (
            "qmt_roll_stage179_stage372_pending_audit_"
            f"{target_date.replace('-', '')}.json"
        )
    )
    pending_target_ready = (
        profile.intraday_stop_retry_enabled
        or (
            str(pending_audit_summary.get("target_date", ""))
            == target_date
            and str(pending_audit_summary.get("execution_profile", ""))
            == profile.profile_key
            and profile.pending_orders_path.exists()
        )
    )
    if args.mode == "plan-only":
        shadow_refresh_status = "shadow_refresh_plan_only"
    elif not blocking.empty:
        shadow_refresh_status = "shadow_refresh_blocked"
    elif any(row["exit_code"] != 0 for row in commands) or len(commands) != len(specs):
        shadow_refresh_status = "shadow_refresh_command_failed"
    elif shadow_target_ready and pending_target_ready:
        shadow_refresh_status = "shadow_refresh_completed"
    else:
        shadow_refresh_status = "shadow_refresh_completed_but_target_not_ready"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": target_date,
        "target_date_mode": args.target_date_mode,
        "target_date_evidence": target_date_evidence,
        "mode": args.mode,
        "execution_profile": profile.profile_key,
        "official_live_version": profile.official_version,
        "official_live_alias": profile.alias,
        "capital": profile.capital,
        "capital_label": profile.capital_label,
        "analysis_start": analysis_start,
        "mapping_start": mapping_start,
        "bar_start": bar_start,
        "shadow_refresh_status": shadow_refresh_status,
        "refresh_attempted": int(refresh_attempted),
        "official_summary_analysis_end_after": official_summary.get("analysis_end", ""),
        "official_summary_generated_at_after": official_summary.get("generated_at", ""),
        "pending_order_audit_target_ready": int(pending_target_ready),
        "blocking_failure_count": int(len(blocking)),
        "commands": commands,
        "sanitized_command_plan": command_plan,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage909 只刷新数据和既定官方 shadow，不改策略参数。",
            "continue_before": "是。全自动必须覆盖信号计算。",
            "overfit_after": "否。刷新闸门不反馈优化。",
            "continue_after": "是。下一步应把 Stage909 纳入 Stage903 控制器。",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
