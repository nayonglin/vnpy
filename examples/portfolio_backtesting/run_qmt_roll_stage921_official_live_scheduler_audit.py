from __future__ import annotations

import argparse
import json
import plistlib
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import build_phase_d_config
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage921_official_live_scheduler_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage921_official_live_scheduler_audit"
STAGE903_MODEL_TAG = "stage903_official_live_phase_d_controller_v1"
STAGE903_PREFIX = "qmt_roll_stage903_official_live_phase_d_controller"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _latest(pattern: str) -> Path | None:
    rows = sorted(OUTPUT_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_plist(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        with path.open("rb") as f:
            return plistlib.load(f)
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_int(value: Any, default: int = -1) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _arg_value(args: list[str], key: str) -> str:
    if key not in args:
        return ""
    idx = args.index(key)
    if idx + 1 >= len(args):
        return ""
    return str(args[idx + 1])


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


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    failed = checks[checks["passed"].eq(0)] if not checks.empty else pd.DataFrame()
    return "\n".join(
        [
            "# Stage921 Official Live Scheduler Audit",
            "",
            f"- Generated at: `{summary['generated_at']}`",
            f"- Official live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- Scheduler status: `{summary['scheduler_status']}`",
            f"- Target date mode: `{summary['target_date_mode']}`",
            f"- Order API calls: `{summary['order_api_called_count']}`",
            "",
            "## Failed Checks",
            "",
            _to_markdown(failed, ["check", "severity", "observed", "required", "blocker"]),
            "",
            "## All Checks",
            "",
            _to_markdown(checks, ["check", "passed", "severity", "observed", "required"]),
            "",
            "## Notes",
            "",
            "- Stage921 is static scheduler evidence only. It does not load CTP, submit orders, or cancel orders.",
            "- A fixed `--target-date` launchd template is acceptable for replay/audit, but not enough to prove unattended daily production operation.",
            "- Full Phase D automation still requires dynamic latest-completed-trading-day resolution plus broker/shadow reconciliation.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live scheduler/launchd audit.")
    parser.add_argument("--stage903-summary", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    config = build_phase_d_config()
    stage903_path = Path(args.stage903_summary) if args.stage903_summary else _latest(
        f"{STAGE903_PREFIX}_summary_*_{STAGE903_MODEL_TAG}.json"
    )
    stage903 = _read_json(stage903_path)
    launchd_path_text = _clean((stage903.get("outputs") or {}).get("launchd_plist"))
    launchd_path = Path(launchd_path_text) if launchd_path_text else _latest(
        f"{STAGE903_PREFIX}_launchd_template_*_{STAGE903_MODEL_TAG}.plist"
    )
    plist = _read_plist(launchd_path)
    program_args = [str(item) for item in plist.get("ProgramArguments", [])] if isinstance(plist, dict) else []
    env_vars = plist.get("EnvironmentVariables", {}) if isinstance(plist.get("EnvironmentVariables"), dict) else {}
    poll_seconds = _to_int(_arg_value(program_args, "--poll-seconds"), -1)
    mode = _arg_value(program_args, "--mode")
    target_date = _arg_value(program_args, "--target-date")
    target_date_mode_arg = _arg_value(program_args, "--target-date-mode")
    target_date_data_ready_time = _arg_value(program_args, "--target-date-data-ready-time")
    shadow_refresh_mode = _arg_value(program_args, "--shadow-refresh-mode")
    readonly_refresh_mode = _arg_value(program_args, "--readonly-refresh-mode")
    target_date_mode = (
        "fixed_target_date"
        if target_date
        else "latest_completed_resolver"
        if target_date_mode_arg == "latest-completed"
        else "dynamic_from_controller_state"
    )
    controller_script_ok = any(item.endswith("run_qmt_roll_stage903_official_live_phase_d_controller.py") for item in program_args)

    checks: list[dict[str, Any]] = []
    _check_row(
        checks,
        check="stage903_summary_present",
        passed=bool(stage903) and not stage903.get("_read_error"),
        severity="block",
        observed=str(stage903_path) if stage903_path else "",
        required="readable Stage903 summary",
        blocker="stage903_summary_missing_or_unreadable",
    )
    _check_row(
        checks,
        check="launchd_plist_present_and_parseable",
        passed=bool(plist) and not plist.get("_read_error"),
        severity="block",
        observed=str(launchd_path) if launchd_path else "",
        required="readable launchd plist",
        blocker="launchd_plist_missing_or_unreadable",
    )
    _check_row(
        checks,
        check="launchd_runs_controller_loop",
        passed=controller_script_ok and "--loop" in program_args,
        severity="block",
        observed=" ".join(program_args),
        required="ProgramArguments includes Stage903 controller and --loop",
        blocker="launchd_controller_loop_missing",
    )
    _check_row(
        checks,
        check="launchd_keepalive_runatload",
        passed=bool(plist.get("KeepAlive")) and bool(plist.get("RunAtLoad")),
        severity="block",
        observed=f"KeepAlive={plist.get('KeepAlive')};RunAtLoad={plist.get('RunAtLoad')}",
        required="KeepAlive=true and RunAtLoad=true",
        blocker="launchd_not_persistent",
    )
    _check_row(
        checks,
        check="poll_seconds_within_hard_limit",
        passed=0 < poll_seconds <= int(config.hard_limits.max_controller_cycle_seconds),
        severity="block",
        observed=poll_seconds,
        required=f"0<poll_seconds<={config.hard_limits.max_controller_cycle_seconds}",
        blocker="controller_poll_interval_out_of_bounds",
    )
    _check_row(
        checks,
        check="launchd_mode_dry_run_or_monitor",
        passed=mode in {"dry-run", "monitor-only"},
        severity="block",
        observed=mode,
        required="launchd template must default to dry-run/monitor-only until final live gate",
        blocker="launchd_mode_not_fail_closed",
    )
    _check_row(
        checks,
        check="launchd_shadow_refresh_auto",
        passed=shadow_refresh_mode == "auto" and "--confirm-shadow-refresh" in program_args,
        severity="block",
        observed=f"shadow_refresh_mode={shadow_refresh_mode};confirm={'--confirm-shadow-refresh' in program_args}",
        required="--shadow-refresh-mode auto with confirmation text",
        blocker="launchd_shadow_refresh_auto_missing",
    )
    _check_row(
        checks,
        check="launchd_readonly_refresh_auto",
        passed=readonly_refresh_mode == "auto" and "--confirm-readonly-refresh" in program_args,
        severity="block",
        observed=f"readonly_refresh_mode={readonly_refresh_mode};confirm={'--confirm-readonly-refresh' in program_args}",
        required="--readonly-refresh-mode auto with confirmation text",
        blocker="launchd_readonly_refresh_auto_missing",
    )
    _check_row(
        checks,
        check="launchd_refresh_env_gates_enabled_real_submit_disabled",
        passed=(
            str(env_vars.get("OFFICIAL_LIVE_PHASE_D_SHADOW_REFRESH_ENABLED", "")) == "1"
            and str(env_vars.get("OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED", "")) == "1"
            and str(env_vars.get("OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED", "")) == "1"
            and str(env_vars.get("OFFICIAL_LIVE_PHASE_D_REAL_ADAPTER_IMPLEMENTED", "")) == "1"
            and not str(env_vars.get("OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED", "")).strip()
        ),
        severity="block",
        observed=json.dumps(env_vars, ensure_ascii=False, sort_keys=True),
        required="shadow/readonly/session/adapter dry-run env enabled; real submit env absent",
        blocker="launchd_env_gates_not_safe_for_full_dry_run",
    )
    _check_row(
        checks,
        check="dynamic_target_date_not_fixed",
        passed=not target_date and target_date_mode_arg == "latest-completed",
        severity="warn",
        observed=f"target_date={target_date or '<empty>'};target_date_mode={target_date_mode_arg or '<empty>'}",
        required="omit --target-date and include --target-date-mode latest-completed",
        blocker="launchd_target_date_fixed",
    )
    _check_row(
        checks,
        check="controller_order_api_zero",
        passed=_to_int(stage903.get("order_api_called_count"), -1) == 0,
        severity="block",
        observed=stage903.get("order_api_called_count", ""),
        required=0,
        blocker="controller_order_api_called",
    )

    checks_df = pd.DataFrame(checks)
    block_failures = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]
    warn_failures = checks_df[checks_df["severity"].eq("warn") & checks_df["passed"].eq(0)]
    if not block_failures.empty:
        scheduler_status = "scheduler_audit_blocked_fail_closed"
    elif not warn_failures.empty:
        scheduler_status = "scheduler_template_fixed_target_date_partial_fail_closed"
    else:
        scheduler_status = "scheduler_template_dynamic_target_ready_fail_closed"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "scheduler_status": scheduler_status,
        "target_date_mode": target_date_mode,
        "target_date": target_date,
        "target_date_mode_arg": target_date_mode_arg,
        "target_date_data_ready_time": target_date_data_ready_time,
        "shadow_refresh_mode": shadow_refresh_mode,
        "readonly_refresh_mode": readonly_refresh_mode,
        "mode": mode,
        "poll_seconds": poll_seconds,
        "block_failure_count": int(len(block_failures)),
        "warn_failure_count": int(len(warn_failures)),
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "source_files": {
            "stage903_summary": str(stage903_path) if stage903_path else "",
            "launchd_plist": str(launchd_path) if launchd_path else "",
        },
        "judgement": {
            "overfit_before": "No. Stage921 audits scheduler evidence only.",
            "continue_before": "Yes. Full automation requires a persistent controller with daily target-date handling.",
            "overfit_after": "No. The audit does not affect strategy signals.",
            "continue_after": "Yes. Scheduler evidence still needs broker/shadow reconciliation before live submit.",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
