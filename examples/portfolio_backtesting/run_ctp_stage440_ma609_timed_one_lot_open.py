#!/usr/bin/env python3
"""Stage440: one-shot timed MA609 one-lot open wrapper.

Default mode is dry-run-only. Real submit requires an explicit mode and the
same confirmation strings enforced by Stage367.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_VERSION

ROOT_DIR = PROJECT_DIR.parents[1]
PYTHON = ROOT_DIR / ".py311" / "bin" / "python"
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage440_ma609_timed_one_lot_open_v1"
OUTPUT_PREFIX = "qmt_roll_stage440_ma609_timed_one_lot_open"
PENDING_AUDIT_PREFIX = "qmt_roll_official_shadow_pending_audit"

STAGE655 = PROJECT_DIR / "run_ctp_stage655_readonly_account_margin_probe.py"
STAGE367 = PROJECT_DIR / "run_ctp_stage367_live_one_lot_order.py"
DEFAULT_ENV_FILE = PROJECT_DIR / "ctp_live.local.env"
STAGE655_OUTPUTS = {
    "summary": OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json",
    "accounts": OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_accounts_stage655_readonly_account_margin_probe_v1.csv",
    "positions": OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv",
    "logs": OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_logs_stage655_readonly_account_margin_probe_v1.csv",
}

CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_REAL_CTP_LIVE_ORDER"
RESIDUAL_CONFIRM_TEXT = "I_UNDERSTAND_THIS_LEAVES_A_REAL_POSITION"


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
    }


def _target_datetime(date_text: str, time_text: str) -> datetime:
    return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _pending_audit_summary_path(target_date: str) -> Path:
    compact_date = target_date.replace("-", "")
    return OUTPUT_DIR / f"{PENDING_AUDIT_PREFIX}_{compact_date}_summary.json"


def _candidate_brief(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "candidate_status",
        "ai_product_pool_allowed",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "selected_volume",
        "planned_entry_price",
        "stop_price",
        "stop_distance",
        "target_risk_amount",
    ]
    return {key: row.get(key, "") for key in keys}


def _official_signal_gate(args: argparse.Namespace) -> dict[str, Any]:
    summary_path = _pending_audit_summary_path(args.target_date)
    gate: dict[str, Any] = {
        "summary_path": str(summary_path.resolve()),
        "passed": False,
        "reason": "",
    }
    if not summary_path.exists():
        gate["reason"] = "pending_audit_summary_missing"
        return gate
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gate["reason"] = f"pending_audit_summary_unreadable:{exc!r}"
        return gate

    gate["official_live_version"] = summary.get("official_live_version", "")
    gate["target_date"] = summary.get("target_date", "")
    gate["pending_order_count"] = _safe_int(summary.get("pending_order_count"))
    gate["current_position_count"] = _safe_int(summary.get("current_position_count"))
    if gate["official_live_version"] != OFFICIAL_LIVE_VERSION:
        gate["reason"] = "official_live_version_mismatch"
        return gate
    if gate["target_date"] != args.target_date:
        gate["reason"] = "target_date_mismatch"
        return gate
    if gate["current_position_count"] != 0:
        gate["reason"] = "shadow_current_position_not_flat"
        return gate

    expected_direction = "Long" if args.direction == "long" else "Short"
    pending_orders = summary.get("pending_orders") or []
    matched_orders = [
        row
        for row in pending_orders
        if str(row.get("vt_symbol", "")) == args.vt_symbol
        and str(row.get("direction", "")).lower() == expected_direction.lower()
        and str(row.get("offset", "")).lower() == "open"
        and str(row.get("status", "")).lower() == "submitting"
        and _safe_int(row.get("volume")) >= _safe_int(args.volume)
    ]
    if not matched_orders:
        gate["reason"] = "matching_pending_open_order_missing"
        return gate

    target_candidates = summary.get("target_opened_candidates") or []
    matched_candidates = [
        row
        for row in target_candidates
        if str(row.get("contract_vt_symbol", "")) == args.vt_symbol
        and str(row.get("direction", "")).lower() == args.direction
        and str(row.get("candidate_status", "")).lower() == "opened"
        and _safe_int(row.get("ai_product_pool_allowed")) == 1
        and _safe_int(row.get("selected_volume")) >= _safe_int(args.volume)
    ]
    if not matched_candidates:
        gate["reason"] = "matching_opened_candidate_missing"
        return gate

    gate["matched_pending_order"] = matched_orders[0]
    gate["matched_opened_candidate"] = _candidate_brief(matched_candidates[0])
    gate["passed"] = True
    return gate


def _sleep_until(label: str, target: datetime, max_late_seconds: int, events: list[dict[str, Any]]) -> None:
    now = datetime.now()
    if now >= target:
        late_seconds = (now - target).total_seconds()
        events.append(
            {
                "event": "target_time_already_passed",
                "label": label,
                "target": target.strftime("%Y-%m-%d %H:%M:%S"),
                "now": _now_text(),
                "late_seconds": round(late_seconds, 3),
            }
        )
        if late_seconds > max_late_seconds:
            raise RuntimeError(f"{label}_missed_by_{late_seconds:.1f}s")
        return

    wait_seconds = (target - now).total_seconds()
    events.append(
        {
            "event": "waiting_until",
            "label": label,
            "target": target.strftime("%Y-%m-%d %H:%M:%S"),
            "now": _now_text(),
            "wait_seconds": round(wait_seconds, 3),
        }
    )
    print(f"[stage440] waiting {wait_seconds:.1f}s until {label} {target:%Y-%m-%d %H:%M:%S}", flush=True)
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1.0))


def _env_bash_command(env_file: Path, extra_env: dict[str, str], args: list[str]) -> list[str]:
    exports = "; ".join(f"export {key}={json.dumps(value)}" for key, value in extra_env.items())
    bootstrap = (
        "set -euo pipefail; "
        'set -a; source "$1"; set +a; shift; '
        'PROJECT_ROOT="$1"; shift; '
        'CTP_FRAMEWORK_DIR="${PROJECT_ROOT}/.py311/lib"; '
        'CTP_LIB_DIR="${PROJECT_ROOT}/.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs"; '
        'export DYLD_FRAMEWORK_PATH="${CTP_LIB_DIR}:${CTP_FRAMEWORK_DIR}${DYLD_FRAMEWORK_PATH:+:${DYLD_FRAMEWORK_PATH}}"; '
    )
    if exports:
        bootstrap += exports + "; "
    bootstrap += 'exec "$@"'
    return ["bash", "-c", bootstrap, "stage440", str(env_file), str(ROOT_DIR), *args]


def _decode_first_json(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _archive_stage655_outputs(run_id: str, step_name: str, min_mtime_epoch: float | None = None) -> dict[str, Any]:
    archived: dict[str, Any] = {"copied": {}, "missing": [], "skipped_stale": []}
    for key, source in STAGE655_OUTPUTS.items():
        if not source.exists():
            archived["missing"].append(key)
            continue
        if min_mtime_epoch is not None and source.stat().st_mtime < min_mtime_epoch - 1.0:
            archived["skipped_stale"].append({"key": key, "source": str(source.resolve())})
            continue
        target = OUTPUT_DIR / f"{OUTPUT_PREFIX}_{step_name}_{run_id}_{key}_{MODEL_TAG}{source.suffix}"
        shutil.copy2(source, target)
        archived["copied"][key] = str(target.resolve())
    return archived


def _run_step(
    *,
    name: str,
    env_file: Path,
    extra_env: dict[str, str],
    args: list[str],
    timeout_seconds: int,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    command = _env_bash_command(env_file, extra_env, args)
    started_at = _now_text()
    started_epoch = time.time()
    stdout_for_json = ""
    print(f"[stage440] starting {name} at {started_at}", flush=True)
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout_for_json = completed.stdout
        result = {
            "event": "step_finished",
            "name": name,
            "started_at": started_at,
            "started_epoch": started_epoch,
            "ended_at": _now_text(),
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-6000:],
            "stderr_tail": completed.stderr[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout_for_json = exc.stdout if isinstance(exc.stdout, str) else ""
        result = {
            "event": "step_timeout",
            "name": name,
            "started_at": started_at,
            "started_epoch": started_epoch,
            "ended_at": _now_text(),
            "returncode": 124,
            "stdout_tail": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-6000:] if isinstance(exc.stderr, str) else "",
            "timeout_seconds": timeout_seconds,
        }
    events.append(result)
    child_summary = _decode_first_json(stdout_for_json)
    if child_summary:
        result["child_summary"] = child_summary
        result["child_status"] = child_summary.get("status", "")
        result["child_outputs"] = child_summary.get("outputs", {})
    if result["stdout_tail"]:
        print(result["stdout_tail"], end="" if result["stdout_tail"].endswith("\n") else "\n", flush=True)
    if result["stderr_tail"]:
        print(result["stderr_tail"], end="" if result["stderr_tail"].endswith("\n") else "\n", flush=True)
    return result


def _minimum_readonly_timeout(args: argparse.Namespace) -> int:
    return max(int(args.readonly_wait_seconds), 1) + 15


def _minimum_submit_timeout(args: argparse.Namespace) -> int:
    return (
        max(int(args.connect_wait_seconds), 1)
        + max(int(args.tick_wait_seconds), 1)
        + max(int(args.fill_wait_seconds), 1)
        + max(int(args.post_cancel_wait_seconds), 1)
        + max(int(args.final_wait_seconds), 0)
        + 30
    )


def _stage655_gate_failure(step: dict[str, Any]) -> str:
    child = step.get("child_summary", {}) or {}
    if child.get("status") != "readonly_account_margin_received":
        return str(child.get("status", "missing_child_status"))
    required_true = [
        "front_connected",
        "auth_ok",
        "login_ok",
        "settlement_ok",
        "account_query_received",
        "position_query_completed",
        "position_query_ok",
    ]
    for key in required_true:
        if not bool(child.get(key)):
            return f"{key}_not_confirmed"
    if int(child.get("account_rows") or 0) < 1:
        return "account_rows_missing"
    if int(child.get("explicit_margin_rows") or 0) < 1:
        return "explicit_margin_rows_missing"
    if int(child.get("position_rows") or 0) != 0:
        return "broker_position_not_flat"
    return ""


def _stage655_args(readonly_wait_seconds: int) -> list[str]:
    return [
        str(PYTHON),
        str(STAGE655),
        "--connect",
        "--wait-seconds",
        str(readonly_wait_seconds),
    ]


def _stage367_args(args: argparse.Namespace, mode: str) -> list[str]:
    command = [
        str(PYTHON),
        str(STAGE367),
        "--mode",
        mode,
        "--vt-symbol",
        args.vt_symbol,
        "--direction",
        args.direction,
        "--volume",
        str(args.volume),
        "--connect-wait-seconds",
        str(args.connect_wait_seconds),
        "--tick-wait-seconds",
        str(args.tick_wait_seconds),
        "--fill-wait-seconds",
        str(args.fill_wait_seconds),
        "--final-wait-seconds",
        str(args.final_wait_seconds),
        "--post-cancel-wait-seconds",
        str(args.post_cancel_wait_seconds),
        "--aggressive-ticks",
        str(args.aggressive_ticks),
        "--max-snapshot-age-seconds",
        str(args.max_snapshot_age_seconds),
    ]
    if mode == "submit-open":
        command.extend(
            [
                "--confirm-submit",
                args.confirm_submit,
                "--confirm-residual-position",
                args.confirm_residual_position,
            ]
        )
    return command


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    paths = _paths(run_id)
    events: list[dict[str, Any]] = []

    env_file = Path(args.env_file).expanduser().resolve()
    check_at = _target_datetime(args.target_date, args.check_at)
    submit_at = _target_datetime(args.target_date, args.submit_at)

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": _now_text(),
        "run_id": run_id,
        "mode": args.mode,
        "target_date": args.target_date,
        "check_at": check_at.strftime("%Y-%m-%d %H:%M:%S"),
        "submit_at": submit_at.strftime("%Y-%m-%d %H:%M:%S"),
        "vt_symbol": args.vt_symbol,
        "direction": args.direction,
        "volume": args.volume,
        "env_file": str(env_file),
        "status": "initialized",
        "failure_reason": "",
        "send_order_intended": int(args.mode == "submit-open"),
        "safety": {
            "one_shot": True,
            "default_mode": "dry-run-only",
            "real_submit_requires_wrapper_switch": "--enable-live-submit-env",
            "real_submit_sets_child_env_switch": "CTP_LIVE_ONE_LOT_ENABLED=1",
            "real_submit_requires_confirm_submit": CONFIRM_TEXT,
            "real_submit_requires_residual_confirm": RESIDUAL_CONFIRM_TEXT,
            "stage367_still_limits_volume_to_one": True,
        },
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "events": events,
    }

    def finish(status: str, reason: str = "") -> dict[str, Any]:
        summary["status"] = status
        summary["failure_reason"] = reason
        paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return summary

    if not env_file.exists():
        return finish("blocked_env_file_missing", str(env_file))
    if submit_at <= check_at:
        return finish("blocked_invalid_schedule", "submit_at_must_be_after_check_at")
    if args.vt_symbol != "MA609.CZCE":
        return finish("blocked_unexpected_symbol", "stage440_is_locked_to_MA609.CZCE")
    if args.direction != "long":
        return finish("blocked_unexpected_direction", "stage440_is_locked_to_long")
    if int(args.volume) != 1:
        return finish("blocked_volume_must_be_one", "volume_must_be_one")
    if args.mode == "submit-open":
        if not args.enable_live_submit_env:
            return finish("blocked_live_submit_env_not_enabled", "enable_live_submit_env_missing")
        if args.confirm_submit != CONFIRM_TEXT:
            return finish("blocked_confirmation_missing", "confirm_submit_text_missing")
        if args.confirm_residual_position != RESIDUAL_CONFIRM_TEXT:
            return finish("blocked_residual_position_confirmation_missing", "residual_position_confirm_text_missing")
    official_signal_gate = _official_signal_gate(args)
    summary["official_signal_gate"] = official_signal_gate
    if not official_signal_gate.get("passed"):
        return finish("blocked_official_signal_gate_not_passed", str(official_signal_gate.get("reason", "")))
    readonly_timeout_floor = _minimum_readonly_timeout(args)
    if args.step_timeout_seconds < readonly_timeout_floor:
        return finish("blocked_step_timeout_too_short", f"step_timeout_seconds<{readonly_timeout_floor}")
    if args.mode == "submit-open":
        submit_timeout_floor = _minimum_submit_timeout(args)
        if args.step_timeout_seconds < submit_timeout_floor:
            return finish("blocked_step_timeout_too_short", f"step_timeout_seconds<{submit_timeout_floor}")

    try:
        _sleep_until("readonly_check", check_at, args.max_check_late_seconds, events)
        readonly = _run_step(
            name="stage655_readonly_check",
            env_file=env_file,
            extra_env={},
            args=_stage655_args(args.readonly_wait_seconds),
            timeout_seconds=args.step_timeout_seconds,
            events=events,
        )
        readonly["archived_outputs"] = _archive_stage655_outputs(
            run_id,
            "readonly_check",
            min_mtime_epoch=float(readonly.get("started_epoch") or 0.0),
        )
        if int(readonly["returncode"]) != 0:
            return finish("blocked_readonly_check_failed", f"returncode={readonly['returncode']}")
        readonly_gate_failure = _stage655_gate_failure(readonly)
        if readonly_gate_failure:
            return finish("blocked_readonly_check_not_passed", readonly_gate_failure)

        if args.mode == "submit-open" and args.refresh_seconds_before_submit >= 0:
            refresh_at = submit_at - timedelta(seconds=args.refresh_seconds_before_submit)
            _sleep_until("pre_submit_readonly_refresh", refresh_at, args.max_check_late_seconds, events)
            refresh = _run_step(
                name="stage655_pre_submit_refresh",
                env_file=env_file,
                extra_env={},
                args=_stage655_args(args.readonly_wait_seconds),
                timeout_seconds=args.step_timeout_seconds,
                events=events,
            )
            refresh["archived_outputs"] = _archive_stage655_outputs(
                run_id,
                "pre_submit_refresh",
                min_mtime_epoch=float(refresh.get("started_epoch") or 0.0),
            )
            if int(refresh["returncode"]) != 0:
                return finish("blocked_pre_submit_refresh_failed", f"returncode={refresh['returncode']}")
            refresh_gate_failure = _stage655_gate_failure(refresh)
            if refresh_gate_failure:
                return finish("blocked_pre_submit_refresh_not_passed", refresh_gate_failure)

        _sleep_until("submit_or_dry_run", submit_at, args.max_submit_late_seconds, events)
        stage367_mode = "submit-open" if args.mode == "submit-open" else "dry-run"
        extra_env = {"CTP_LIVE_ONE_LOT_ENABLED": "1"} if args.mode == "submit-open" and args.enable_live_submit_env else {}
        submit = _run_step(
            name=f"stage367_{stage367_mode}",
            env_file=env_file,
            extra_env=extra_env,
            args=_stage367_args(args, stage367_mode),
            timeout_seconds=args.step_timeout_seconds,
            events=events,
        )
        if int(submit["returncode"]) != 0:
            return finish("stage367_failed", f"returncode={submit['returncode']}")
        child = submit.get("child_summary", {})
        child_status = str(child.get("status", ""))
        if not child_status:
            return finish("stage367_summary_missing")
        if args.mode == "dry-run-only":
            if child_status == "dry_run_request_ready":
                return finish("completed_dry_run_ready", child_status)
            return finish("blocked_stage367_not_ready", child_status)

        send_order_count = int(child.get("send_order_api_called_count") or 0)
        cancel_order_count = int(child.get("cancel_order_api_called_count") or 0)
        summary["stage367_send_order_api_called_count"] = send_order_count
        summary["stage367_cancel_order_api_called_count"] = cancel_order_count
        summary["stage367_vt_orderid"] = child.get("vt_orderid", "")
        if child_status == "submit_open_filled_residual_position_exists":
            return finish("completed_submit_filled", child_status)
        if child_status == "submit-open_not_filled_cancel_confirmed":
            return finish("review_submit_not_filled_cancel_confirmed_needs_reconcile", child_status)
        if child_status in {"submit-open_not_filled_cancel_attempted", "submit-open_cancel_outcome_uncertain"}:
            return finish("review_submit_cancel_outcome_uncertain", child_status)
        if send_order_count > 0:
            return finish("review_submit_order_api_called_outcome_uncertain", child_status)
        return finish("blocked_stage367_no_order_sent", child_status)
    except Exception as exc:
        return finish("exception", repr(exc))


def main() -> None:
    default_date = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="One-shot timed MA609 one-lot live open wrapper.")
    parser.add_argument("--mode", choices=["dry-run-only", "submit-open"], default="dry-run-only")
    parser.add_argument("--target-date", default=default_date)
    parser.add_argument("--check-at", default="20:55:00")
    parser.add_argument("--submit-at", default="21:00:01")
    parser.add_argument("--refresh-seconds-before-submit", type=int, default=90)
    parser.add_argument("--vt-symbol", default="MA609.CZCE")
    parser.add_argument("--direction", choices=["long", "short"], default="long")
    parser.add_argument("--volume", type=int, default=1)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--readonly-wait-seconds", type=int, default=35)
    parser.add_argument("--connect-wait-seconds", type=int, default=8)
    parser.add_argument("--tick-wait-seconds", type=int, default=20)
    parser.add_argument("--fill-wait-seconds", type=int, default=10)
    parser.add_argument("--final-wait-seconds", type=int, default=3)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=5)
    parser.add_argument("--aggressive-ticks", type=int, default=2)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--max-check-late-seconds", type=int, default=600)
    parser.add_argument("--max-submit-late-seconds", type=int, default=30)
    parser.add_argument("--step-timeout-seconds", type=int, default=180)
    parser.add_argument("--enable-live-submit-env", action="store_true")
    parser.add_argument("--confirm-submit", default="")
    parser.add_argument("--confirm-residual-position", default="")
    args = parser.parse_args()

    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
