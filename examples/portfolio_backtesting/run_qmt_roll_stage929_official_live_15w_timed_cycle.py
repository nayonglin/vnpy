from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_ENV,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
    PHASE_D_SHADOW_REFRESH_ENV,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PYTHON_PATH = REPO_ROOT / ".py311/bin/python"
STAGE903_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage903_official_live_phase_d_controller.py"

MODEL_TAG = "stage929_official_live_15w_timed_cycle_v1"
OUTPUT_PREFIX = "qmt_roll_stage929_official_live_15w_timed_cycle"
LATEST_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_summary.json"
LATEST_REPORT_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_report.md"
LATEST_COMMAND_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_command.log"


def _date_key(value: str) -> str:
    return value.replace("-", "") if value else "latest"


def _paths(phase: str, target_date: str, run_id: str) -> dict[str, Path]:
    key = f"{phase}_{_date_key(target_date)}_{run_id}"
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{key}_{MODEL_TAG}.md",
        "command_log": OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_log_{key}_{MODEL_TAG}.log",
    }


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def _latest_stage903_summary() -> Path | None:
    rows = sorted(
        OUTPUT_DIR.glob("qmt_roll_stage903_official_live_phase_d_controller_summary_*_stage903_official_live_phase_d_controller_v1.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return rows[0] if rows else None


def _parse_stage903_stdout(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.rfind("\n{")
    if start >= 0:
        try:
            return json.loads(text[start + 1 :])
        except json.JSONDecodeError:
            return {}
    return {}


def _account_snapshot() -> dict[str, Any]:
    accounts = _read_csv_maybe(
        OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_accounts_stage174_ctp_vnpy_readonly_probe_v1.csv"
    )
    positions = _read_csv_maybe(
        OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_positions_stage174_ctp_vnpy_readonly_probe_v1.csv"
    )
    snapshot: dict[str, Any] = {
        "account_rows": int(len(accounts)),
        "position_rows": int(len(positions)),
    }
    if not accounts.empty:
        row = accounts.iloc[-1]
        for column in ("balance", "available", "frozen"):
            if column in accounts.columns:
                snapshot[column] = float(pd.to_numeric(row[column], errors="coerce"))
    if not positions.empty:
        volume = pd.to_numeric(positions.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        snapshot["nonzero_position_rows"] = int((volume != 0).sum())
        snapshot["position_volume_sum"] = float(volume.sum())
    return snapshot


def _stage903_command(args: argparse.Namespace, target_date: str) -> list[str]:
    return [
        str(PYTHON_PATH),
        str(STAGE903_SCRIPT),
        "--target-date",
        target_date,
        "--mode",
        "dry-run",
        "--shadow-refresh-mode",
        args.shadow_refresh_mode,
        "--confirm-shadow-refresh",
        PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        "--readonly-refresh-mode",
        args.readonly_refresh_mode,
        "--readonly-env-profile",
        "production-live",
        "--readonly-wait-seconds",
        str(args.readonly_wait_seconds),
        "--confirm-readonly-refresh",
        PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
        "--stage251-mode",
        "skip",
        "--max-snapshot-age-seconds",
        str(args.max_snapshot_age_seconds),
    ]


def _stage903_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env[PHASE_D_SHADOW_REFRESH_ENV] = "1"
    env[PHASE_D_READONLY_REFRESH_ENV] = "1"
    env[PHASE_D_SESSION_DAEMON_ENV] = "1"
    env[PHASE_D_REAL_ADAPTER_ENV] = "1"
    env.pop(PHASE_D_REAL_ENABLED_ENV, None)
    return env


def _run_stage903(args: argparse.Namespace, target_date: str, log_path: Path) -> tuple[int, dict[str, Any]]:
    cmd = _stage903_command(args, target_date)
    env = _stage903_env()
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.timeout_seconds,
        check=False,
    )
    finished = datetime.now()
    log_path.write_text(
        "\n".join(
            [
                f"started_at={started:%Y-%m-%d %H:%M:%S}",
                f"finished_at={finished:%Y-%m-%d %H:%M:%S}",
                f"exit_code={result.returncode}",
                "$ " + " ".join(cmd),
                "",
                result.stdout,
            ]
        ),
        encoding="utf-8",
    )
    summary = _parse_stage903_stdout(result.stdout)
    if not summary:
        summary = _read_json(_latest_stage903_summary())
    summary["_stage903_wrapper_exit_code"] = result.returncode
    summary["_stage903_command"] = cmd
    summary["_stage903_command_log"] = str(log_path.resolve())
    return result.returncode, summary


def _status_text(summary: dict[str, Any]) -> str:
    pending = int(pd.to_numeric(summary.get("pending_order_count", 0), errors="coerce") or 0)
    executable = int(pd.to_numeric(summary.get("stage260_executable_count", 0), errors="coerce") or 0)
    order_api = int(pd.to_numeric(summary.get("order_api_called_count", 0), errors="coerce") or 0)
    controller_status = str(summary.get("controller_status", ""))
    if order_api:
        return "异常：检测到 order API 调用，必须立即人工复核。"
    if executable > 0:
        return "有 dry-run 可执行候选；真实报单仍未启用，需要人工复核后另走 live gate。"
    if pending > 0:
        return "有理论 pending order，但 broker/dry-run 闸门未放行或需要人工复核。"
    if "blocked" in controller_status:
        return "没有可自动执行交易；控制器处于 fail-closed/block 状态。"
    return "没有可自动执行交易；当前链路只生成报告和 dry-run 状态。"


def _build_report(wrapper: dict[str, Any], stage903: dict[str, Any]) -> str:
    account = wrapper.get("account_snapshot", {}) or {}
    stage903_outputs = stage903.get("outputs", {}) if isinstance(stage903.get("outputs"), dict) else {}
    return "\n".join(
        [
            "# C9/15w 官方自动化晚间报告",
            "",
            f"- 生成时间：`{wrapper['generated_at']}`",
            f"- 运行阶段：`{wrapper['phase']}`",
            f"- 目标日期：`{wrapper['target_date']}`",
            f"- 当前版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            f"- Shadow 起点：`{OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE}`",
            f"- 总结：{_status_text(stage903)}",
            "",
            "## 核心状态",
            "",
            f"- Controller：`{stage903.get('controller_status', '')}`",
            f"- Session：`{stage903.get('current_session_names', '')}`",
            f"- Stage909 shadow：`{stage903.get('stage909_shadow_refresh_status', '')}`，effective mode `{stage903.get('stage909_effective_shadow_refresh_mode', '')}`，attempted `{stage903.get('stage909_refresh_attempted', '')}`",
            f"- Stage907 readonly：`{stage903.get('stage907_refresh_status', '')}`，effective mode `{stage903.get('stage907_effective_refresh_mode', '')}`",
            f"- Stage902 readiness：`{stage903.get('stage902_overall_status', '')}`，blockers `{stage903.get('stage902_blocking_failure_count', '')}`",
            f"- Stage260 execution gate：executable `{stage903.get('stage260_executable_count', '')}`，blocked `{stage903.get('stage260_blocked_count', '')}`，skipped_flat `{stage903.get('stage260_skipped_flat_count', '')}`",
            f"- Stage905 executor dry-run：`{stage903.get('stage905_executor_status', '')}`，ready `{stage903.get('stage905_ready_count', '')}`，blocked `{stage903.get('stage905_blocked_count', '')}`",
            f"- Signal rows：`{stage903.get('signal_count', '')}`，pending orders：`{stage903.get('pending_order_count', '')}`，current positions：`{stage903.get('current_position_count', '')}`",
            f"- Order API calls：`{stage903.get('order_api_called_count', '')}`",
            "",
            "## 账户只读快照",
            "",
            f"- balance：`{account.get('balance', '')}`",
            f"- available：`{account.get('available', '')}`",
            f"- position rows：`{account.get('position_rows', '')}`，nonzero rows：`{account.get('nonzero_position_rows', 0)}`",
            "",
            "## 报告文件",
            "",
            f"- Stage903 report：`{stage903_outputs.get('report_md', '')}`",
            f"- Stage903 summary：`{stage903_outputs.get('summary_json', '')}`",
            f"- Wrapper command log：`{wrapper.get('command_log', '')}`",
            "",
            "## 执行纪律",
            "",
            "- 本自动化只运行 shadow、read-only、dry-run 和报告链路。",
            "- `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED` 未设置，真实报单默认关闭。",
            "- 若出现 pending order，也必须先看 broker 持仓/资金对账和 readiness/dry-run 结果；空仓账户不得执行历史 shadow 平仓回放。",
            "",
        ]
    )


def _write_outputs(paths: dict[str, Path], wrapper: dict[str, Any], stage903: dict[str, Any]) -> None:
    payload = dict(wrapper)
    payload["stage903_summary"] = stage903
    report = _build_report(wrapper, stage903)
    paths["summary_json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(report, encoding="utf-8")
    LATEST_SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LATEST_REPORT_PATH.write_text(report, encoding="utf-8")
    if paths["command_log"].exists():
        LATEST_COMMAND_LOG_PATH.write_text(paths["command_log"].read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Timed dry-run/report wrapper for official C9/15w live automation.")
    parser.add_argument("--phase", choices=["post-close", "evening-report", "manual"], default="manual")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--shadow-refresh-mode", choices=["plan-only", "run", "auto"], default="auto")
    parser.add_argument("--readonly-refresh-mode", choices=["plan-only", "refresh", "auto"], default="auto")
    parser.add_argument("--readonly-wait-seconds", type=int, default=30)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--allow-weekend", action="store_true")
    args = parser.parse_args()

    now = datetime.now()
    target_date = args.target_date or date.today().isoformat()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.phase, target_date, run_id)

    if now.weekday() >= 5 and not args.allow_weekend:
        stage903_summary: dict[str, Any] = {
            "controller_status": "stage929_weekend_noop",
            "target_date": target_date,
            "order_api_called_count": 0,
            "signal_count": 0,
            "pending_order_count": 0,
            "current_position_count": 0,
        }
        exit_code = 0
        paths["command_log"].write_text("weekend_noop\n", encoding="utf-8")
    else:
        exit_code, stage903_summary = _run_stage903(args, target_date, paths["command_log"])

    wrapper = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "phase": args.phase,
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_shadow_analysis_start_date": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
        "wrapper_exit_code": exit_code,
        "order_api_called_count": stage903_summary.get("order_api_called_count", 0),
        "account_snapshot": _account_snapshot(),
        "command_log": str(paths["command_log"].resolve()),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "latest_outputs": {
            "summary_json": str(LATEST_SUMMARY_PATH.resolve()),
            "report_md": str(LATEST_REPORT_PATH.resolve()),
            "command_log": str(LATEST_COMMAND_LOG_PATH.resolve()),
        },
        "judgement": {
            "overfit_before": "否。Stage929 是定时执行包装器，不改策略参数。",
            "continue_before": "是。用户需要 21 点后直接看稳定路径的报告。",
            "overfit_after": "否。包装器只汇总 Stage903/只读/dry-run 输出。",
            "continue_after": "是。下一步是看日终数据是否成功刷新以及 pending/dry-run 是否出现。",
        },
    }
    _write_outputs(paths, wrapper, stage903_summary)
    print(json.dumps({"wrapper": wrapper, "stage903_summary": stage903_summary}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
