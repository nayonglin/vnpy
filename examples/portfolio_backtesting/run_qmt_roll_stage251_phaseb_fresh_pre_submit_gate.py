from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage251_phaseb_fresh_pre_submit_gate_v1"
SCRIPT_DIR = Path(__file__).resolve().parent
READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"


def _paths(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "summary_json": OUTPUT_DIR / f"qmt_roll_stage251_phaseb_fresh_pre_submit_gate_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"qmt_roll_stage251_phaseb_fresh_pre_submit_gate_report_{date_key}_{MODEL_TAG}.md",
        "command_log": OUTPUT_DIR / f"qmt_roll_stage251_phaseb_fresh_pre_submit_gate_command_log_{date_key}_{MODEL_TAG}.txt",
        "readonly_summary": READONLY_SUMMARY_PATH,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_generated_at(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _run_command(name: str, cmd: list[str], env: dict[str, str], log_path: Path) -> dict[str, Any]:
    started = datetime.now()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n\n===== {name} | {started:%Y-%m-%d %H:%M:%S} =====\n")
        log.write("$ " + " ".join(cmd) + "\n")
        result = subprocess.run(
            cmd,
            cwd=SCRIPT_DIR.parent.parent,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
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


def _positive(summary: dict[str, Any], key: str) -> bool:
    try:
        return int(summary.get(key, 0)) > 0
    except Exception:
        return False


def _zero(summary: dict[str, Any], key: str) -> bool:
    try:
        return int(summary.get(key, 0)) == 0
    except Exception:
        return False


def _readonly_snapshot_ready(summary: dict[str, Any]) -> bool:
    broker_snapshot = summary.get("broker_snapshot", {})
    return (
        summary.get("status") == "readonly_snapshots_received"
        and str(broker_snapshot.get("position_snapshot_state", "")) in {"confirmed_flat", "positions_received"}
    )


def _build_report(summary: dict[str, Any]) -> str:
    checks = summary["checks"]
    command_lines = [
        f"| {row['name']} | {row['exit_code']} | {row['duration_seconds']} |"
        for row in summary["commands"]
    ]
    if not command_lines:
        command_lines = ["| _empty_ | | |"]
    check_lines = [
        f"| {name} | {value} |"
        for name, value in checks.items()
    ]
    return "\n".join(
        [
            "# Stage251 Phase B Fresh Pre-submit Gate",
            "",
            f"- 交易日：`{summary['trade_date']}`",
            f"- 只读连接来源：`{summary['readonly_wrapper']}`",
            f"- SimNow 前置：`{summary['simnow_front']}`",
            f"- 等待秒数：`{summary['wait_seconds']}`",
            f"- 最大快照年龄秒数：`{summary['max_snapshot_age_seconds']}`",
            f"- 最终状态：`{summary['overall_status']}`",
            f"- 阻断原因：`{summary['failure_reason']}`",
            f"- 真实 submit/send_order 调用次数：`{summary['total_order_api_called_count']}`",
            "",
            "## 检查项",
            "",
            "| check | value |",
            "|:--|:--|",
            *check_lines,
            "",
            "## 命令",
            "",
            "| step | exit_code | duration_seconds |",
            "|:--|--:|--:|",
            *command_lines,
            "",
            "## 说明",
            "",
            "- 本阶段会重新连接 CTP/SimNow 做只读快照，但不调用真实下单 API。",
            "- `fresh_pre_submit_gate_passed` 只表示最后一刻提交前闸门通过，不等于已经提交订单。",
            "- 真实提交仍需另一个 adapter 明确实现，并再次保留环境变量与人工确认开关。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fresh read-only probe and final dry-run pre-submit gate.")
    parser.add_argument("--trade-date", required=True, help="Trade date, YYYY-MM-DD.")
    parser.add_argument("--wait-seconds", type=int, default=90)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--simnow-front", default=os.getenv("SIMNOW_FRONT", "trading"))
    parser.add_argument(
        "--readonly-wrapper",
        choices=("simnow", "broker-test"),
        default=os.getenv("CTP_READONLY_WRAPPER", "simnow"),
        help="Which CTP read-only wrapper to refresh before pre-submit checks.",
    )
    parser.add_argument("--skip-real-block-test", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.trade_date)
    paths["command_log"].write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["SIMNOW_FRONT"] = args.simnow_front
    commands: list[dict[str, Any]] = []

    readonly_wrapper_script = {
        "simnow": "run_ctp_stage177_simnow_readonly_probe.sh",
        "broker-test": "run_ctp_stage267_broker_test_readonly_probe.sh",
    }[args.readonly_wrapper]

    command_specs: list[tuple[str, list[str]]] = [
        (
            "stage174_fresh_readonly_probe",
            [
                "bash",
                str(SCRIPT_DIR / readonly_wrapper_script),
                "--connect",
                "--wait-seconds",
                str(args.wait_seconds),
            ],
        ),
        (
            "stage244_pre_submit_check",
            [
                sys.executable,
                str(SCRIPT_DIR / "run_qmt_roll_stage244_phaseb_pre_submit_check.py"),
                "--trade-date",
                args.trade_date,
            ],
        ),
        (
            "stage245_duplicate_target_check",
            [
                sys.executable,
                str(SCRIPT_DIR / "run_qmt_roll_stage245_phaseb_duplicate_and_target_checks.py"),
                "--trade-date",
                args.trade_date,
            ],
        ),
        (
            "stage249_submit_adapter_dry_run",
            [
                sys.executable,
                str(SCRIPT_DIR / "run_qmt_roll_stage249_phaseb_submit_adapter.py"),
                "--trade-date",
                args.trade_date,
                "--mode",
                "dry-run",
            ],
        ),
        (
            "stage250_order_request_builder_dry_run",
            [
                sys.executable,
                str(SCRIPT_DIR / "run_qmt_roll_stage250_phaseb_vnpy_order_request_builder.py"),
                "--trade-date",
                args.trade_date,
                "--mode",
                "dry-run",
            ],
        ),
    ]
    if not args.skip_real_block_test:
        command_specs.append(
            (
                "stage250_order_request_builder_real_block_test",
                [
                    sys.executable,
                    str(SCRIPT_DIR / "run_qmt_roll_stage250_phaseb_vnpy_order_request_builder.py"),
                    "--trade-date",
                    args.trade_date,
                    "--mode",
                    "real",
                ],
            )
        )

    for name, cmd in command_specs:
        row = _run_command(name, cmd, env, paths["command_log"])
        commands.append(row)
        if row["exit_code"] != 0:
            break
        if name == "stage174_fresh_readonly_probe" and not _readonly_snapshot_ready(_read_json(READONLY_SUMMARY_PATH)):
            break

    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    stage244_summary = _read_json(OUTPUT_DIR / f"qmt_roll_stage244_phaseb_pre_submit_check_summary_{args.trade_date.replace('-', '')}_stage244_phaseb_pre_submit_check_v1.json")
    stage245_summary = _read_json(OUTPUT_DIR / f"qmt_roll_stage245_phaseb_duplicate_target_summary_{args.trade_date.replace('-', '')}_stage245_phaseb_duplicate_and_target_checks_v1.json")
    stage249_summary = _read_json(OUTPUT_DIR / f"qmt_roll_stage249_phaseb_submit_adapter_summary_{args.trade_date.replace('-', '')}_stage249_phaseb_submit_adapter_v1.json")
    stage250_dry_summary = _read_json(OUTPUT_DIR / f"qmt_roll_stage250_phaseb_vnpy_order_request_builder_dry_run_summary_{args.trade_date.replace('-', '')}_stage250_phaseb_vnpy_order_request_builder_v1.json")
    stage250_real_summary = _read_json(OUTPUT_DIR / f"qmt_roll_stage250_phaseb_vnpy_order_request_builder_real_summary_{args.trade_date.replace('-', '')}_stage250_phaseb_vnpy_order_request_builder_v1.json")

    generated_at = str(readonly_summary.get("generated_at", ""))
    generated_dt = _parse_generated_at(generated_at)
    snapshot_age_seconds = None
    if generated_dt:
        snapshot_age_seconds = round((datetime.now() - generated_dt).total_seconds(), 3)

    broker_snapshot = readonly_summary.get("broker_snapshot", {})
    position_state = str(broker_snapshot.get("position_snapshot_state", ""))
    total_order_api_called = sum(
        int(summary.get(key, 0) or 0)
        for summary, key in [
            (readonly_summary, "order_api_called"),
            (stage249_summary, "submit_api_called_count"),
            (stage250_dry_summary, "order_api_called_count"),
            (stage250_real_summary, "order_api_called_count"),
        ]
    )

    executed_names = {row["name"] for row in commands}
    all_commands_ok = all(row["exit_code"] == 0 for row in commands) and len(commands) == len(command_specs)
    checks: dict[str, Any] = {
        "all_commands_ok": all_commands_ok,
        "readonly_status": readonly_summary.get("status", ""),
        "readonly_snapshot_state": position_state,
        "snapshot_age_seconds": snapshot_age_seconds,
        "snapshot_fresh": snapshot_age_seconds is not None and snapshot_age_seconds <= args.max_snapshot_age_seconds,
        "stage244_passed": (
            _positive(stage244_summary, "passed_count") and _zero(stage244_summary, "failed_count")
            if "stage244_pre_submit_check" in executed_names
            else "not_run"
        ),
        "stage245_final_can_submit": (
            _positive(stage245_summary, "final_can_submit_count") and _zero(stage245_summary, "blocked_count")
            if "stage245_duplicate_target_check" in executed_names
            else "not_run"
        ),
        "stage249_dry_run_ready": (
            _positive(stage249_summary, "dry_run_ready_count") and _zero(stage249_summary, "submit_api_called_count")
            if "stage249_submit_adapter_dry_run" in executed_names
            else "not_run"
        ),
        "stage250_dry_request_ready": (
            _positive(stage250_dry_summary, "request_ready_count") and _zero(stage250_dry_summary, "order_api_called_count")
            if "stage250_order_request_builder_dry_run" in executed_names
            else "not_run"
        ),
        "stage250_real_blocked": (
            bool(args.skip_real_block_test)
            or (_positive(stage250_real_summary, "blocked_count") and _zero(stage250_real_summary, "order_api_called_count"))
            if "stage250_order_request_builder_real_block_test" in executed_names
            else "not_run"
        ),
        "total_order_api_called_zero": total_order_api_called == 0,
    }

    failures = [name for name, passed in checks.items() if isinstance(passed, bool) and not passed]
    if readonly_summary.get("status") != "readonly_snapshots_received":
        failures.append("readonly_status_not_snapshots_received")
    if position_state not in {"confirmed_flat", "positions_received"}:
        failures.append("position_snapshot_not_confirmed")

    overall_status = "fresh_pre_submit_gate_passed" if not failures else "fresh_pre_submit_gate_blocked"
    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": args.trade_date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "readonly_wrapper": args.readonly_wrapper,
        "simnow_front": args.simnow_front,
        "wait_seconds": args.wait_seconds,
        "max_snapshot_age_seconds": args.max_snapshot_age_seconds,
        "snapshot_generated_at": generated_at,
        "snapshot_age_seconds": snapshot_age_seconds,
        "overall_status": overall_status,
        "failure_reason": ";".join(dict.fromkeys(failures)),
        "total_order_api_called_count": total_order_api_called,
        "commands": commands,
        "checks": checks,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。即时再探针只检查执行状态新鲜度，不改策略参数。",
            "continue_before": "是。真实提交不能复用陈旧账户/持仓/挂单快照。",
            "overfit_after": "否。闸门只决定是否允许继续，不影响历史收益。",
            "continue_after": "是。若持续通过，下一步才是最小真实 submit adapter；若失败，应先处理账户状态或连接问题。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
