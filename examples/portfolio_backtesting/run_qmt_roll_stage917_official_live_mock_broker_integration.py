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
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    READONLY_CONTRACTS_PATH,
    READONLY_ORDERS_PATH,
    READONLY_POSITIONS_PATH,
    READONLY_SUMMARY_PATH,
    READONLY_TICKS_PATH,
    READONLY_TRADES_PATH,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
MODEL_TAG = "stage917_official_live_mock_broker_integration_v1"
OUTPUT_PREFIX = "qmt_roll_stage917_official_live_mock_broker_integration"

READONLY_ACCOUNTS_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_accounts_stage174_ctp_vnpy_readonly_probe_v1.csv"
READONLY_LOGS_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_logs_stage174_ctp_vnpy_readonly_probe_v1.csv"
READONLY_POSITION_CALLBACKS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_position_query_callbacks_stage174_ctp_vnpy_readonly_probe_v1.csv"
)

STAGE260_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py"
STAGE902_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage902_official_live_phase_d_readiness_gate.py"
STAGE904_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage904_official_live_c9_intraday_monitor.py"
STAGE905_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage905_official_live_executor_dry_run.py"
STAGE906_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage906_official_live_reconciliation_worker.py"
STAGE908_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage908_official_live_submit_adapter_contract.py"


def _date_key(target_date: str) -> str:
    return target_date.replace("-", "") if target_date else "latest"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "child_summaries_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_child_summaries_{run_id}_{MODEL_TAG}.json",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _stage_paths(target_date: str) -> list[Path]:
    date_key = _date_key(target_date)
    return [
        OUTPUT_DIR / f"qmt_roll_stage251_phaseb_fresh_pre_submit_gate_summary_{date_key}_stage251_phaseb_fresh_pre_submit_gate_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage260_official_live_daily_execution_gate_decisions_{date_key}_stage260_official_live_daily_execution_gate_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage260_official_live_daily_execution_gate_summary_{date_key}_stage260_official_live_daily_execution_gate_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage260_official_live_daily_execution_gate_report_{date_key}_stage260_official_live_daily_execution_gate_v1.md",
        OUTPUT_DIR / f"qmt_roll_stage902_official_live_phase_d_readiness_gate_checks_{date_key}_stage902_official_live_phase_d_readiness_gate_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage902_official_live_phase_d_readiness_gate_summary_{date_key}_stage902_official_live_phase_d_readiness_gate_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage902_official_live_phase_d_readiness_gate_report_{date_key}_stage902_official_live_phase_d_readiness_gate_v1.md",
        OUTPUT_DIR / f"qmt_roll_stage904_official_live_c9_intraday_monitor_actions_{date_key}_stage904_official_live_c9_intraday_monitor_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage904_official_live_c9_intraday_monitor_summary_{date_key}_stage904_official_live_c9_intraday_monitor_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage904_official_live_c9_intraday_monitor_report_{date_key}_stage904_official_live_c9_intraday_monitor_v1.md",
        OUTPUT_DIR / f"qmt_roll_stage905_official_live_executor_dry_run_intents_{date_key}_stage905_official_live_executor_dry_run_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage905_official_live_executor_dry_run_summary_{date_key}_stage905_official_live_executor_dry_run_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage905_official_live_executor_dry_run_report_{date_key}_stage905_official_live_executor_dry_run_v1.md",
        OUTPUT_DIR / f"qmt_roll_stage906_official_live_reconciliation_worker_checks_{date_key}_stage906_official_live_reconciliation_worker_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage906_official_live_reconciliation_worker_position_diff_{date_key}_stage906_official_live_reconciliation_worker_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage906_official_live_reconciliation_worker_summary_{date_key}_stage906_official_live_reconciliation_worker_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage906_official_live_reconciliation_worker_report_{date_key}_stage906_official_live_reconciliation_worker_v1.md",
        OUTPUT_DIR / f"qmt_roll_stage908_official_live_submit_adapter_contract_checks_{date_key}_stage908_official_live_submit_adapter_contract_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage908_official_live_submit_adapter_contract_submit_batch_{date_key}_stage908_official_live_submit_adapter_contract_v1.csv",
        OUTPUT_DIR / f"qmt_roll_stage908_official_live_submit_adapter_contract_summary_{date_key}_stage908_official_live_submit_adapter_contract_v1.json",
        OUTPUT_DIR / f"qmt_roll_stage908_official_live_submit_adapter_contract_report_{date_key}_stage908_official_live_submit_adapter_contract_v1.md",
    ]


def _readonly_paths() -> list[Path]:
    return [
        READONLY_SUMMARY_PATH,
        READONLY_ACCOUNTS_PATH,
        READONLY_POSITIONS_PATH,
        READONLY_ORDERS_PATH,
        READONLY_TRADES_PATH,
        READONLY_CONTRACTS_PATH,
        READONLY_TICKS_PATH,
        READONLY_LOGS_PATH,
        READONLY_POSITION_CALLBACKS_PATH,
    ]


class FileTransaction:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = list(dict.fromkeys(paths))
        self.backups: dict[Path, bytes | None] = {}

    def __enter__(self) -> "FileTransaction":
        for path in self.paths:
            self.backups[path] = path.read_bytes() if path.exists() else None
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.restore()

    def restore(self) -> None:
        for path, payload in self.backups.items():
            if payload is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

    def verify_restored(self) -> dict[str, Any]:
        mismatches: list[str] = []
        for path, payload in self.backups.items():
            if payload is None:
                if path.exists():
                    mismatches.append(str(path))
            elif not path.exists() or path.read_bytes() != payload:
                mismatches.append(str(path))
        return {"restored": int(not mismatches), "mismatch_paths": mismatches}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False, encoding="utf-8-sig")


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_mock_readonly_snapshot() -> None:
    now = _now_text()
    outputs = {
        "accounts": str(READONLY_ACCOUNTS_PATH.resolve()),
        "positions": str(READONLY_POSITIONS_PATH.resolve()),
        "orders": str(READONLY_ORDERS_PATH.resolve()),
        "trades": str(READONLY_TRADES_PATH.resolve()),
        "contracts": str(READONLY_CONTRACTS_PATH.resolve()),
        "ticks": str(READONLY_TICKS_PATH.resolve()),
        "logs": str(READONLY_LOGS_PATH.resolve()),
        "position_query_callbacks": str(READONLY_POSITION_CALLBACKS_PATH.resolve()),
    }
    _write_csv(
        READONLY_ACCOUNTS_PATH,
        [
            {
                "accountid": "STAGE917_MOCK",
                "balance": 300000.0,
                "available": 240000.0,
                "margin": 43344.0,
                "gateway_name": "CTP",
                "snapshot_at": now,
            }
        ],
        ["accountid", "balance", "available", "margin", "gateway_name", "snapshot_at"],
    )
    _write_csv(
        READONLY_POSITIONS_PATH,
        [
            {
                "vt_symbol": "MA609.CZCE",
                "symbol": "MA609",
                "exchange": "CZCE",
                "direction": "long",
                "volume": 12,
                "frozen": 0,
                "price": 3010.0,
                "gateway_name": "CTP",
                "snapshot_at": now,
            }
        ],
        ["vt_symbol", "symbol", "exchange", "direction", "volume", "frozen", "price", "gateway_name", "snapshot_at"],
    )
    _write_csv(
        READONLY_ORDERS_PATH,
        [],
        ["vt_orderid", "orderid", "vt_symbol", "direction", "offset", "price", "volume", "traded", "datetime", "status", "gateway_name"],
    )
    _write_csv(
        READONLY_TRADES_PATH,
        [],
        ["vt_tradeid", "tradeid", "vt_orderid", "vt_symbol", "direction", "offset", "price", "volume", "datetime", "gateway_name"],
    )
    _write_csv(
        READONLY_CONTRACTS_PATH,
        [
            {
                "vt_symbol": "MA609.CZCE",
                "symbol": "MA609",
                "exchange": "CZCE",
                "name": "mock_MA609",
                "product": "FUTURES",
                "size": 10,
                "pricetick": 1.0,
                "min_volume": 1,
                "max_volume": 999,
                "gateway_name": "CTP",
                "snapshot_at": now,
            }
        ],
        ["vt_symbol", "symbol", "exchange", "name", "product", "size", "pricetick", "min_volume", "max_volume", "gateway_name", "snapshot_at"],
    )
    _write_mock_ticks()
    _write_csv(
        READONLY_LOGS_PATH,
        [{"time": now, "level": "INFO", "message": "stage917 mock readonly snapshot", "gateway_name": "CTP"}],
        ["time", "level", "message", "gateway_name"],
    )
    _write_csv(
        READONLY_POSITION_CALLBACKS_PATH,
        [{"time": now, "callback": "position_snapshot_mocked", "row_count": 1}],
        ["time", "callback", "row_count"],
    )
    _write_json(
        READONLY_SUMMARY_PATH,
        {
            "model_tag": "stage174_ctp_vnpy_readonly_probe_v1",
            "generated_at": now,
            "status": "readonly_snapshots_received",
            "front_connected": True,
            "login_success": True,
            "mock_generated_by_stage917": 1,
            "broker_snapshot": {
                "account_snapshot_state": "account_received",
                "position_snapshot_state": "positions_received",
                "order_snapshot_state": "orders_received",
                "trade_snapshot_state": "trades_received",
                "contract_snapshot_state": "contracts_received",
                "tick_snapshot_state": "ticks_received",
                "position_rows": 1,
                "nonzero_position_rows": 1,
                "active_order_rows": 0,
            },
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called_count": 0,
            "outputs": outputs,
        },
    )


def _write_mock_ticks() -> None:
    now = _now_text()
    _write_csv(
        READONLY_TICKS_PATH,
        [
            {
                "vt_symbol": "MA609.CZCE",
                "symbol": "MA609",
                "exchange": "CZCE",
                "last_price": 3004.0,
                "bid_price_1": 3004.0,
                "ask_price_1": 3005.0,
                "limit_up": 999999.0,
                "limit_down": 1.0,
                "localtime": now,
                "datetime": now,
                "gateway_name": "CTP",
            }
        ],
        [
            "vt_symbol",
            "symbol",
            "exchange",
            "last_price",
            "bid_price_1",
            "ask_price_1",
            "limit_up",
            "limit_down",
            "localtime",
            "datetime",
            "gateway_name",
        ],
    )


def _write_mock_stage251(target_date: str) -> Path:
    path = _stage_paths(target_date)[0]
    _write_json(
        path,
        {
            "model_tag": "stage251_phaseb_fresh_pre_submit_gate_v1",
            "generated_at": _now_text(),
            "trade_date": target_date,
            "overall_status": "fresh_pre_submit_gate_passed",
            "mock_generated_by_stage917": 1,
            "total_order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        },
    )
    return path


def _run_child(name: str, cmd: list[str], summary_path: Path, env_extra: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    if env_extra:
        env.update(env_extra)
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
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
        "stdout_tail": result.stdout[-4000:],
        "summary_path": str(summary_path.resolve()),
        "summary": _read_json(summary_path),
    }


def _stage_summary_path(prefix: str, target_date: str, model_tag: str) -> Path:
    return OUTPUT_DIR / f"{prefix}_summary_{_date_key(target_date)}_{model_tag}.json"


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _check(rows: list[dict[str, Any]], check: str, passed: bool, observed: Any, required: Any, blocker: str = "") -> None:
    rows.append(
        {
            "check": check,
            "passed": int(bool(passed)),
            "observed": observed,
            "required": required,
            "blocker": "" if passed else blocker or check,
            "checked_at": _now_text(),
        }
    )


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    failed = checks[checks["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage917 Official Live Mock Broker Integration",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- mock integration 状态：`{summary['mock_integration_status']}`",
            f"- 真实快照恢复：`{summary['real_snapshot_restored']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Failed Checks",
            "",
            failed.to_markdown(index=False) if not failed.empty else "_empty_",
            "",
            "## All Checks",
            "",
            checks.to_markdown(index=False) if not checks.empty else "_empty_",
            "",
            "## 说明",
            "",
            "- Stage917 使用 mock broker 快照证明执行链路语义，不连接 CTP，不提交委托。",
            "- 该脚本会恢复 Stage174 真实快照文件和目标日 Stage260/902/904/905/906/908 子阶段输出。",
            "- mock 通过不能替代生产 CTP fresh read-only 通过；真实无人值守前仍需 Stage907/Stage902/Stage906 在真实快照下通过。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock-broker integration proof for official Phase D automation.")
    parser.add_argument("--target-date", required=True)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    tx_paths = _readonly_paths() + _stage_paths(args.target_date)
    commands: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    restore_result: dict[str, Any] = {"restored": 0, "mismatch_paths": ["transaction_not_entered"]}

    tx = FileTransaction(tx_paths)
    try:
        with tx:
            _write_mock_readonly_snapshot()
            _write_mock_stage251(args.target_date)
            env_gates = {PHASE_D_SESSION_DAEMON_ENV: "1", PHASE_D_REAL_ADAPTER_ENV: "1"}

            commands.append(
                _run_child(
                    "stage260_pending_order_execution_gate",
                    [sys.executable, str(STAGE260_SCRIPT), "--max-snapshot-age-seconds", "300"],
                    _stage_summary_path(
                        "qmt_roll_stage260_official_live_daily_execution_gate",
                        args.target_date,
                        "stage260_official_live_daily_execution_gate_v1",
                    ),
                )
            )
            commands.append(
                _run_child(
                    "stage902_dry_run_readiness",
                    [
                        sys.executable,
                        str(STAGE902_SCRIPT),
                        "--target-date",
                        args.target_date,
                        "--mode",
                        "dry-run",
                        "--max-snapshot-age-seconds",
                        "300",
                    ],
                    _stage_summary_path(
                        "qmt_roll_stage902_official_live_phase_d_readiness_gate",
                        args.target_date,
                        "stage902_official_live_phase_d_readiness_gate_v1",
                    ),
                    env_extra=env_gates,
                )
            )
            _write_mock_ticks()
            commands.append(
                _run_child(
                    "stage904_c9_intraday_monitor",
                    [sys.executable, str(STAGE904_SCRIPT), "--target-date", args.target_date, "--max-tick-age-seconds", "10"],
                    _stage_summary_path(
                        "qmt_roll_stage904_official_live_c9_intraday_monitor",
                        args.target_date,
                        "stage904_official_live_c9_intraday_monitor_v1",
                    ),
                )
            )
            commands.append(
                _run_child(
                    "stage905_executor_dry_run",
                    [sys.executable, str(STAGE905_SCRIPT), "--target-date", args.target_date, "--mode", "dry-run"],
                    _stage_summary_path(
                        "qmt_roll_stage905_official_live_executor_dry_run",
                        args.target_date,
                        "stage905_official_live_executor_dry_run_v1",
                    ),
                )
            )
            commands.append(
                _run_child(
                    "stage906_reconciliation",
                    [sys.executable, str(STAGE906_SCRIPT), "--target-date", args.target_date, "--max-snapshot-age-seconds", "300"],
                    _stage_summary_path(
                        "qmt_roll_stage906_official_live_reconciliation_worker",
                        args.target_date,
                        "stage906_official_live_reconciliation_worker_v1",
                    ),
                )
            )
            commands.append(
                _run_child(
                    "stage908_submit_adapter_contract",
                    [sys.executable, str(STAGE908_SCRIPT), "--target-date", args.target_date, "--mode", "dry-run"],
                    _stage_summary_path(
                        "qmt_roll_stage908_official_live_submit_adapter_contract",
                        args.target_date,
                        "stage908_official_live_submit_adapter_contract_v1",
                    ),
                )
            )
    finally:
        tx.restore()
        restore_result = tx.verify_restored()

    child = {row["name"]: row.get("summary", {}) for row in commands}
    exits_ok = all(row.get("exit_code") == 0 for row in commands)
    stage260 = child.get("stage260_pending_order_execution_gate", {})
    stage902 = child.get("stage902_dry_run_readiness", {})
    stage904 = child.get("stage904_c9_intraday_monitor", {})
    stage905 = child.get("stage905_executor_dry_run", {})
    stage906 = child.get("stage906_reconciliation", {})
    stage908 = child.get("stage908_submit_adapter_contract", {})

    order_api_called = max(
        _to_int(stage260.get("order_api_called_count"), 0),
        _to_int(stage902.get("order_api_called_count"), 0),
        _to_int(stage904.get("order_api_called_count"), 0),
        _to_int(stage905.get("send_order_api_called_count"), 0),
        _to_int(stage905.get("cancel_order_api_called_count"), 0),
        _to_int(stage906.get("order_api_called_count"), 0),
        _to_int(stage908.get("order_api_called_count"), 0),
    )

    _check(checks, "child_processes_exit_zero", exits_ok, [row.get("exit_code") for row in commands], "all 0")
    _check(checks, "stage260_uses_pending_order_and_executable", _to_int(stage260.get("executable_count"), 0) > 0, stage260.get("executable_count"), ">0")
    _check(
        checks,
        "stage902_dry_run_blocking_zero",
        stage902.get("overall_status") == "phase_d_readiness_dry_run_passed_real_still_disabled"
        and _to_int(stage902.get("blocking_failure_count"), -1) == 0,
        f"{stage902.get('overall_status')};blocking={stage902.get('blocking_failure_count')}",
        "dry-run passed with zero blockers",
    )
    _check(checks, "stage904_close_dry_run", _to_int(stage904.get("close_dry_run_count"), 0) > 0, stage904.get("close_dry_run_count"), ">0")
    _check(
        checks,
        "stage905_ready_intent",
        stage905.get("executor_status") == "executor_dry_run_ready"
        and _to_int(stage905.get("ready_count"), 0) > 0
        and _to_int(stage905.get("blocked_count"), -1) == 0,
        f"{stage905.get('executor_status')};ready={stage905.get('ready_count')};blocked={stage905.get('blocked_count')}",
        "executor_dry_run_ready + ready>0 + blocked=0",
    )
    _check(
        checks,
        "stage906_reconcile_aligned",
        stage906.get("reconciliation_status") == "reconcile_aligned",
        f"{stage906.get('reconciliation_status')};{stage906.get('account_state_alignment')}",
        "reconcile_aligned",
    )
    _check(
        checks,
        "stage908_real_submit_still_blocked",
        _to_int(stage908.get("live_submit_permitted"), -1) == 0 and _to_int(stage908.get("order_api_called_count"), -1) == 0,
        f"live_submit={stage908.get('live_submit_permitted')};order_api={stage908.get('order_api_called_count')}",
        "live_submit_permitted=0 and order_api=0",
    )
    _check(checks, "real_snapshot_and_child_outputs_restored", bool(restore_result.get("restored")), restore_result, "all transactional files restored")
    _check(checks, "no_order_api_called", order_api_called == 0, order_api_called, 0)

    checks_df = pd.DataFrame(checks)
    passed = int(checks_df["passed"].sum()) if not checks_df.empty else 0
    failed = int((checks_df["passed"] == 0).sum()) if not checks_df.empty else 0
    status = (
        "mock_broker_state_gate_reconcile_passed_real_submit_still_blocked"
        if failed == 0
        else "mock_broker_integration_failed_fail_closed"
    )
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": _now_text(),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "mock_integration_status": status,
        "passed_count": passed,
        "failed_count": failed,
        "real_snapshot_restored": int(bool(restore_result.get("restored"))),
        "restore_result": restore_result,
        "order_api_called_count": int(order_api_called),
        "connect_attempted": 0,
        "real_broker_order_api_called_count": 0,
        "child_statuses": {
            "stage260": stage260.get("executable_count", ""),
            "stage902": stage902.get("overall_status", ""),
            "stage904": stage904.get("monitor_status", ""),
            "stage905": stage905.get("executor_status", ""),
            "stage906": stage906.get("reconciliation_status", ""),
            "stage908": stage908.get("adapter_contract_status", ""),
        },
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage917 用固定 mock broker 快照验证执行链路，不改 C9 策略参数。",
            "continue_before": "是。全自动必须证明 fresh broker 状态下 signal/gate/executor/reconcile 能闭合。",
            "overfit_after": "否。mock 只验证工程语义，不用于调参或替代真实 CTP 证据。",
            "continue_after": "是。mock 通过后仍需生产 CTP read-only fresh 快照下重跑 Stage260/902/905/906。",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    _write_json(paths["child_summaries_json"], {"commands": commands})
    _write_json(paths["summary_json"], summary)
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
