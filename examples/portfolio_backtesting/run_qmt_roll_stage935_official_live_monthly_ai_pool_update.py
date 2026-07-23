from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from qmt_roll_official_live_lightweight_context import (
    ALL_FUTURES_MAPPING_PATH,
    CONTROL_OUTPUT_DIR,
    DATA_ASSET_DIR,
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_VERSION,
    STAGE173_SUMMARY_PATH,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification


MODEL_TAG = "stage935_official_live_monthly_ai_pool_update_v1"
OUTPUT_PREFIX = "qmt_roll_stage935_official_live_monthly_ai_pool_update"
DEFAULT_SOURCE_PREFIX = "qmt_roll_stage183_ai_source_floor35"
STAGE182_MODEL_TAG = "stage182_ai_product_pool_live_inference_v1"
STAGE182_OUTPUT_PREFIX = "qmt_roll_stage182_ai_product_pool_live_inference"
STAGE183_MODEL_TAG = "stage183_ai_product_pool_source_refresh_v1"
STAGE183_OUTPUT_PREFIX = "qmt_roll_stage183_ai_product_pool_source_refresh"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_PATH = PROJECT_ROOT / ".py311/bin/python"
PROJECT_DIR = Path(__file__).resolve().parent
STAGE173_PATH = PROJECT_DIR / "build_qmt_roll_stage173_forward_main_contract_data_update.py"
STAGE182_PATH = PROJECT_DIR / "build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py"
STAGE183_PATH = PROJECT_DIR / "build_qmt_roll_stage183_ai_product_pool_source_refresh.py"
STAGE182_SUMMARY_PATH = (
    DATA_ASSET_DIR / f"{STAGE182_OUTPUT_PREFIX}_summary_{STAGE182_MODEL_TAG}.json"
)
STAGE182_LIVE_ELIGIBILITY_PATH = (
    DATA_ASSET_DIR
    / f"{STAGE182_OUTPUT_PREFIX}_eligibility_{STAGE182_MODEL_TAG}.csv"
)
STAGE182_COMBINED_ELIGIBILITY_PATH = (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
)
STAGE183_SUMMARY_PATH = (
    DATA_ASSET_DIR / f"{STAGE183_OUTPUT_PREFIX}_summary_{STAGE183_MODEL_TAG}.json"
)
LOCK_PATH = CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}.lock"
MISSING_CALENDAR_UPDATE_REASON = "trading_calendar_stale_before_wall_clock_cutoff"
RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS = 4
BLOCKING_STATUSES = {
    "monthly_ai_pool_update_blocked",
    "monthly_ai_pool_exception",
    "monthly_ai_pool_update_needed",
    "monthly_ai_pool_locked",
}


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json"
        ),
        "report_txt": (
            CONTROL_OUTPUT_DIR
            / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.txt"
        ),
        "latest_summary_json": (
            CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_summary.json"
        ),
        "latest_report_txt": (
            CONTROL_OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_report.txt"
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).date().isoformat()


def _timestamp(value: str) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).normalize()


def _tail(text: str, limit: int = 4000) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[-limit:]


def _run_command(cmd: list[str], timeout: int) -> dict[str, Any]:
    started_at = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "elapsed_seconds": round(time.time() - started_at, 2),
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "exit_code": -1,
            "elapsed_seconds": round(time.time() - started_at, 2),
            "stdout_tail": "",
            "stderr_tail": repr(exc),
        }


def _parse_as_of(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now()
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _parse_time_minutes(value: str) -> int:
    hour, minute = str(value).split(":", 1)
    return int(hour) * 60 + int(minute)


def _previous_weekday(day: pd.Timestamp) -> pd.Timestamp:
    current = day.normalize()
    while current.weekday() >= 5:
        current -= pd.Timedelta(days=1)
    return current


@contextmanager
def _stage935_lock(enabled: bool) -> Iterator[dict[str, Any]]:
    if not enabled:
        yield {"lock_status": "lock_disabled"}
        return
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("w", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            yield {
                "lock_status": "lock_busy",
                "lock_path": str(LOCK_PATH.resolve()),
            }
            return
        handle.write(f"pid={os.getpid()} started_at={datetime.now():%Y-%m-%d %H:%M:%S}\n")
        handle.flush()
        yield {
            "lock_status": "lock_acquired",
            "lock_path": str(LOCK_PATH.resolve()),
            "lock_pid": os.getpid(),
        }
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass


def _wall_clock_cutoff_date(as_of: datetime, data_ready_time: str) -> pd.Timestamp:
    ready_minutes = _parse_time_minutes(data_ready_time)
    as_of_minutes = as_of.hour * 60 + as_of.minute
    day = pd.Timestamp(as_of.date()).normalize()
    if as_of.weekday() < 5 and as_of_minutes < ready_minutes:
        day -= pd.Timedelta(days=1)
    return _previous_weekday(day)


def _known_trading_dates() -> pd.Series:
    if not ALL_FUTURES_MAPPING_PATH.exists():
        return pd.Series(dtype="datetime64[ns]")
    frame = _read_csv(ALL_FUTURES_MAPPING_PATH)
    if frame.empty or "date" not in frame.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame["date"], errors="coerce").dropna().drop_duplicates().sort_values().reset_index(drop=True)


def _resolve_latest_completed(as_of: datetime, data_ready_time: str) -> tuple[str, dict[str, Any]]:
    cutoff = _wall_clock_cutoff_date(as_of, data_ready_time)
    trading_dates = _known_trading_dates()
    known_max = pd.Timestamp(trading_dates.iloc[-1]).normalize() if not trading_dates.empty else None
    calendar_lag_days = int((cutoff - known_max).days) if known_max is not None else None
    calendar_stale = bool(known_max is not None and known_max < cutoff)
    eligible = trading_dates[trading_dates <= cutoff]
    if not eligible.empty:
        resolved = pd.Timestamp(eligible.iloc[-1]).normalize()
        source = "main_contract_mapping_trading_calendar"
    else:
        resolved = _previous_weekday(cutoff)
        source = "weekday_fallback"
    evidence = {
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "data_ready_time": data_ready_time,
        "wall_clock_cutoff_date": cutoff.date().isoformat(),
        "trading_calendar_source": source,
        "known_trading_date_count": int(len(trading_dates)),
        "known_trading_date_max": (known_max.date().isoformat() if known_max is not None else ""),
        "calendar_lag_days": calendar_lag_days if calendar_lag_days is not None else "",
        "calendar_stale_before_cutoff": int(calendar_stale),
    }
    return resolved.date().isoformat(), evidence


def _calendar_stale_requires_update(resolver_evidence: dict[str, Any]) -> bool:
    known_max = _timestamp(str(resolver_evidence.get("known_trading_date_max", "")))
    cutoff = _timestamp(str(resolver_evidence.get("wall_clock_cutoff_date", "")))
    if known_max is None or cutoff is None:
        return False
    if known_max >= cutoff:
        return False
    # The mapping calendar is the source used to decide which month is complete.
    # Once the wall-clock cutoff has moved beyond it, especially across a month
    # boundary, using the stale calendar to declare the AI pool current is circular.
    return True


def _expected_monthly_eval_date(resolved_target_date: str) -> str:
    target = _timestamp(resolved_target_date)
    if target is None:
        return ""
    dates = _known_trading_dates()
    if dates.empty:
        return ""
    month_start = pd.Timestamp(year=target.year, month=target.month, day=1)
    completed = dates[(dates <= target) & (dates < month_start)]
    if completed.empty:
        return ""
    latest_month = pd.Timestamp(completed.iloc[-1]).to_period("M")
    month_dates = completed[completed.dt.to_period("M") == latest_month]
    if month_dates.empty:
        return ""
    return pd.Timestamp(month_dates.iloc[-1]).date().isoformat()


def _recent_monthly_eval_dates(expected_eval_date: str, lookback_months: int) -> list[str]:
    expected_ts = _timestamp(expected_eval_date)
    if expected_ts is None:
        return []
    dates = _known_trading_dates()
    if dates.empty:
        return []
    completed = dates[dates <= expected_ts].copy()
    if completed.empty:
        return []
    month_ends = (
        completed.groupby(completed.dt.to_period("M"))
        .max()
        .sort_values()
        .tail(int(lookback_months))
    )
    return [pd.Timestamp(value).date().isoformat() for value in month_ends.tolist()]


def _combined_eval_date_audit(expected_eval_date: str) -> dict[str, Any]:
    combined = _read_csv(STAGE182_COMBINED_ELIGIBILITY_PATH)
    strategy = "ai_top8_plus_fu_satellite_post_signal_entry_filter"
    result: dict[str, Any] = {
        "path": str(STAGE182_COMBINED_ELIGIBILITY_PATH),
        "exists": bool(STAGE182_COMBINED_ELIGIBILITY_PATH.exists()),
        "shadow_analysis_start_date": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
        "recent_eval_date_lookback_months": RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS,
        "required_recent_eval_dates": _recent_monthly_eval_dates(
            expected_eval_date,
            RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS,
        ),
        "missing_recent_eval_dates": [],
        "row_counts_by_required_eval_date": {},
    }
    if combined.empty or "eval_date" not in combined.columns:
        result["missing_recent_eval_dates"] = list(result["required_recent_eval_dates"])
        return result
    if "strategy" in combined.columns:
        combined = combined[combined["strategy"].astype(str).eq(strategy)].copy()
    if combined.empty:
        result["missing_recent_eval_dates"] = list(result["required_recent_eval_dates"])
        return result
    combined["eval_date"] = pd.to_datetime(combined["eval_date"], errors="coerce").dt.date.astype(str)
    row_counts = combined.groupby("eval_date").size().to_dict()
    required_dates = list(result["required_recent_eval_dates"])
    result["row_counts_by_required_eval_date"] = {
        date: int(row_counts.get(date, 0)) for date in required_dates
    }
    result["missing_recent_eval_dates"] = [
        date for date in required_dates if int(row_counts.get(date, 0)) <= 0
    ]
    return result


def _month_start(value: str) -> str:
    parsed = _timestamp(value)
    if parsed is None:
        return ""
    return pd.Timestamp(year=parsed.year, month=parsed.month, day=1).date().isoformat()


def _validate_stage182_outputs(expected_eval_date: str = "") -> dict[str, Any]:
    summary = _read_json(STAGE182_SUMMARY_PATH)
    blockers: list[str] = []
    warnings: list[str] = []
    eval_date = _date_text(summary.get("eval_date", ""))
    source_max_date = _date_text(summary.get("source_max_date", ""))
    top_products: list[str] = []

    if not summary:
        blockers.append("stage182_summary_missing")
    elif summary.get("_read_error"):
        blockers.append("stage182_summary_read_error")
    if expected_eval_date and eval_date != expected_eval_date:
        blockers.append("stage182_eval_date_not_expected")
    if not eval_date:
        blockers.append("stage182_eval_date_missing")
    if eval_date and source_max_date:
        eval_ts = _timestamp(eval_date)
        source_ts = _timestamp(source_max_date)
        if eval_ts is not None and source_ts is not None and source_ts < eval_ts:
            blockers.append("stage182_source_max_before_eval_date")

    safety = summary.get("safety") or {}
    if safety.get("overwrites_official_stage78_eligibility") not in {False, 0}:
        blockers.append("stage182_safety_overwrites_official_enabled")
    if safety.get("uses_future_label_for_eval_date") not in {False, 0}:
        blockers.append("stage182_safety_future_label_enabled")
    if safety.get("real_order_enabled") not in {False, 0}:
        blockers.append("stage182_safety_real_order_enabled")
    if STAGE182_COMBINED_ELIGIBILITY_PATH.resolve() != OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.resolve():
        blockers.append("official_live_ai_eligibility_path_not_stage182_combined")

    live_eligibility = _read_csv(STAGE182_LIVE_ELIGIBILITY_PATH)
    combined = _read_csv(STAGE182_COMBINED_ELIGIBILITY_PATH)
    if live_eligibility.empty:
        blockers.append("stage182_live_eligibility_missing_or_empty")
    if combined.empty:
        blockers.append("stage182_combined_eligibility_missing_or_empty")
    if eval_date and not live_eligibility.empty and "eval_date" in live_eligibility.columns:
        rows = live_eligibility[live_eligibility["eval_date"].astype(str).eq(eval_date)].copy()
        if len(rows) < 9:
            blockers.append("stage182_live_eligibility_eval_rows_less_than_9")
        if "product_vt_symbol" in rows.columns:
            top_products = rows.sort_values(["score_rank", "product_vt_symbol"], kind="stable")[
                "product_vt_symbol"
            ].astype(str).tolist()
    if eval_date and not combined.empty and "eval_date" in combined.columns:
        combined_rows = combined[combined["eval_date"].astype(str).eq(eval_date)].copy()
        if combined_rows.empty:
            blockers.append("stage182_combined_missing_eval_date_rows")
    if top_products and "fu.SHFE" not in top_products:
        warnings.append("stage182_top9_missing_fixed_fu_satellite")
    combined_eval_date_audit = _combined_eval_date_audit(expected_eval_date)
    if combined_eval_date_audit.get("missing_recent_eval_dates"):
        blockers.append("stage182_combined_missing_recent_eval_dates")

    return {
        "validation_status": "valid" if not blockers else "invalid",
        "blockers": blockers,
        "warnings": warnings,
        "eval_date": eval_date,
        "source_max_date": source_max_date,
        "top_products": top_products,
        "summary_path": str(STAGE182_SUMMARY_PATH),
        "live_eligibility_path": str(STAGE182_LIVE_ELIGIBILITY_PATH),
        "combined_eligibility_path": str(STAGE182_COMBINED_ELIGIBILITY_PATH),
        "official_live_ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "combined_eval_date_audit": combined_eval_date_audit,
    }


def _build_base_summary(args: argparse.Namespace) -> dict[str, Any]:
    as_of = _parse_as_of(str(args.as_of or ""))
    resolved_target_date, resolver_evidence = _resolve_latest_completed(as_of, str(args.data_ready_time))
    expected_eval_date = _expected_monthly_eval_date(resolved_target_date)
    current_validation = _validate_stage182_outputs(expected_eval_date=expected_eval_date)
    current_eval_date = current_validation.get("eval_date", "")
    update_reasons: list[str] = []
    current_ts = _timestamp(str(current_eval_date))
    expected_ts = _timestamp(str(expected_eval_date))

    if _calendar_stale_requires_update(resolver_evidence):
        update_reasons.append(MISSING_CALENDAR_UPDATE_REASON)
    if not expected_eval_date:
        update_reasons.append("expected_eval_date_unresolved")
    elif current_ts is None:
        update_reasons.append("current_stage182_eval_date_missing")
    elif expected_ts is not None and current_ts < expected_ts:
        update_reasons.append("current_stage182_eval_date_stale")
    if current_validation.get("validation_status") != "valid":
        update_reasons.append("current_stage182_outputs_invalid")
    if bool(args.force):
        update_reasons.append("force_requested")

    return {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "mode": str(args.mode),
        "source_prefix": str(args.source_prefix),
        "data_ready_time": str(args.data_ready_time),
        "as_of": as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "resolved_target_date": resolved_target_date,
        "expected_eval_date": expected_eval_date,
        "current_eval_date": current_eval_date,
        "current_stage182_validation": current_validation,
        "resolver_evidence": resolver_evidence,
        "update_reasons": update_reasons,
        "commands": {},
        "blockers": [],
        "warnings": list(current_validation.get("warnings") or []),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "real_order_enabled": False,
        "judgement": {
            "overfit_before": "否。Stage935 只按完整月份刷新 AI 池文件，不改排序模型、策略参数或信号规则。",
            "continue_before": "是。月度 AI 池如果依赖人工刷新，会直接破坏实盘设计中的月更口径。",
            "overfit_after": "否。输出只用于执行接线和安全校验，不根据交易结果反向挑参。",
            "continue_after": "是。后续应把 Stage935 纳入自动化健康检查，确保池子 stale 时能自动修复或 fail-closed。",
        },
    }


def _mark_blocked(summary: dict[str, Any], reason: str) -> dict[str, Any]:
    blockers = list(summary.get("blockers") or [])
    blockers.append(reason)
    summary["blockers"] = blockers
    summary["automation_status"] = "monthly_ai_pool_update_blocked"
    summary["action"] = "blocked_fail_closed"
    return summary


def _execute_update(summary: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    expected_eval_date = str(summary.get("expected_eval_date") or "")
    resolved_target_date = str(summary.get("resolved_target_date") or "")
    source_prefix = str(args.source_prefix)
    if not expected_eval_date or not resolved_target_date:
        return _mark_blocked(summary, "expected_or_resolved_date_missing")

    data_start = _month_start(expected_eval_date)
    if MISSING_CALENDAR_UPDATE_REASON in set(summary.get("update_reasons") or []):
        data_start = _month_start(str(summary.get("resolver_evidence", {}).get("known_trading_date_max", ""))) or data_start
        wall_clock_cutoff = _date_text((summary.get("resolver_evidence") or {}).get("wall_clock_cutoff_date", ""))
        if wall_clock_cutoff:
            resolved_target_date = wall_clock_cutoff
            summary["resolved_target_date"] = resolved_target_date
            summary["calendar_stale_recovery_target_date"] = resolved_target_date
    if not bool(args.skip_data_update):
        stage173_cmd = [
            str(PYTHON_PATH),
            str(STAGE173_PATH),
            "--mapping-start",
            data_start,
            "--bar-start",
            data_start,
            "--end",
            resolved_target_date,
        ]
        stage173_result = _run_command(stage173_cmd, timeout=int(args.data_update_timeout_seconds))
        summary["commands"]["stage173_data_update"] = stage173_result
        if stage173_result.get("exit_code") != 0:
            return _mark_blocked(summary, "stage173_data_update_failed")
        stage173_summary = _read_json(STAGE173_SUMMARY_PATH)
        summary["stage173_summary"] = {
            "path": str(STAGE173_SUMMARY_PATH),
            "max_saved_date": stage173_summary.get("max_saved_date", ""),
            "failed_count": stage173_summary.get("failed_count", 0),
            "empty_count": stage173_summary.get("empty_count", 0),
            "mapping_combined_max_date": (stage173_summary.get("mapping_update") or {}).get("combined_max_date", ""),
        }
        if int(stage173_summary.get("failed_count", 0) or 0) > 0:
            return _mark_blocked(summary, "stage173_failed_contracts_present")
        if _date_text(stage173_summary.get("max_saved_date", "")) != resolved_target_date:
            return _mark_blocked(summary, "stage173_max_saved_date_not_resolved_target_date")
        if MISSING_CALENDAR_UPDATE_REASON in set(summary.get("update_reasons") or []):
            refreshed_target_date, refreshed_evidence = _resolve_latest_completed(
                _parse_as_of(str(args.as_of or "")),
                str(args.data_ready_time),
            )
            refreshed_expected = _expected_monthly_eval_date(refreshed_target_date)
            summary["post_stage173_resolver_evidence"] = refreshed_evidence
            summary["resolved_target_date"] = refreshed_target_date
            summary["expected_eval_date"] = refreshed_expected
            expected_eval_date = refreshed_expected
            resolved_target_date = refreshed_target_date
            if not expected_eval_date:
                return _mark_blocked(summary, "expected_eval_date_unresolved_after_stage173")

    stage183_cmd = [
        str(PYTHON_PATH),
        str(STAGE183_PATH),
        "--analysis-end",
        resolved_target_date,
        "--source-prefix",
        source_prefix,
    ]
    stage183_result = _run_command(stage183_cmd, timeout=int(args.source_refresh_timeout_seconds))
    summary["commands"]["stage183_source_refresh"] = stage183_result
    if stage183_result.get("exit_code") != 0:
        return _mark_blocked(summary, "stage183_source_refresh_failed")

    stage182_cmd = [
        str(PYTHON_PATH),
        str(STAGE182_PATH),
        "--source-prefix",
        source_prefix,
    ]
    stage182_result = _run_command(stage182_cmd, timeout=int(args.inference_timeout_seconds))
    summary["commands"]["stage182_live_inference"] = stage182_result
    if stage182_result.get("exit_code") != 0:
        return _mark_blocked(summary, "stage182_live_inference_failed")

    post_validation = _validate_stage182_outputs(expected_eval_date=expected_eval_date)
    summary["post_stage182_validation"] = post_validation
    stage183_summary = _read_json(STAGE183_SUMMARY_PATH)
    summary["stage183_summary"] = {
        "path": str(STAGE183_SUMMARY_PATH),
        "analysis_end": stage183_summary.get("analysis_end", ""),
        "source_prefix": stage183_summary.get("source_prefix", ""),
        "artifact_dates": stage183_summary.get("artifact_dates", {}),
        "safety": stage183_summary.get("safety", {}),
    }
    if post_validation.get("validation_status") != "valid":
        summary["blockers"] = list(summary.get("blockers") or []) + list(post_validation.get("blockers") or [])
        return _mark_blocked(summary, "post_stage182_validation_failed")

    summary["automation_status"] = "monthly_ai_pool_updated"
    summary["action"] = "stage183_source_refresh_and_stage182_live_inference_completed"
    summary["current_eval_date"] = post_validation.get("eval_date", "")
    summary["top_products"] = post_validation.get("top_products", [])
    return summary


def _run(args: argparse.Namespace) -> dict[str, Any]:
    summary = _build_base_summary(args)
    update_reasons = list(summary.get("update_reasons") or [])
    current_validation = summary.get("current_stage182_validation") or {}
    if not update_reasons:
        summary["automation_status"] = "monthly_ai_pool_already_current"
        summary["action"] = "skipped_no_update_needed"
        summary["top_products"] = current_validation.get("top_products", [])
        return summary
    if "expected_eval_date_unresolved" in update_reasons:
        return _mark_blocked(summary, "expected_eval_date_unresolved")
    if str(args.mode) == "check":
        summary["automation_status"] = "monthly_ai_pool_update_needed"
        summary["action"] = "check_only_no_update"
        return summary
    return _execute_update(summary, args)


def _exit_code_for_status(status: str) -> int:
    return 2 if status in BLOCKING_STATUSES else 0


def _build_report(summary: dict[str, Any]) -> str:
    commands = summary.get("commands") or {}
    command_lines: list[str] = []
    for name, result in commands.items():
        command_lines.append(
            f"{name}: exit={result.get('exit_code')} elapsed={result.get('elapsed_seconds')}s"
        )
    top_products = summary.get("top_products") or (summary.get("current_stage182_validation") or {}).get("top_products") or []
    combined_audit = (
        (summary.get("post_stage182_validation") or {}).get("combined_eval_date_audit")
        or (summary.get("current_stage182_validation") or {}).get("combined_eval_date_audit")
        or {}
    )
    lines = [
        "Stage935 官方实盘月度 AI 池自动更新",
        "",
        f"生成时间：{summary.get('generated_at', '')}",
        f"状态：{summary.get('automation_status', '')}",
        f"动作：{summary.get('action', '')}",
        f"实盘版本：{summary.get('official_live_version', '')}",
        f"最新完成交易日：{summary.get('resolved_target_date', '')}",
        f"应使用 AI 池 eval_date：{summary.get('expected_eval_date', '')}",
        f"当前 Stage182 eval_date：{summary.get('current_eval_date', '')}",
        f"最近需保留月度截面：{', '.join(map(str, combined_audit.get('required_recent_eval_dates') or [])) or '未读取'}",
        f"缺失月度截面：{', '.join(map(str, combined_audit.get('missing_recent_eval_dates') or [])) or '无'}",
        f"更新原因：{';'.join(summary.get('update_reasons') or []) or '无'}",
        f"Top9 品种：{', '.join(map(str, top_products)) or '未读取'}",
        f"阻断：{';'.join(summary.get('blockers') or []) or '无'}",
        f"警告：{';'.join(summary.get('warnings') or []) or '无'}",
        f"下单 API 次数：{summary.get('order_api_called_count', 0)}",
        f"撤单 API 次数：{summary.get('cancel_order_api_called_count', 0)}",
        "",
        "命令结果：",
        *(command_lines if command_lines else ["无"]),
        "",
        "反思：",
        f"运行前过拟合：{(summary.get('judgement') or {}).get('overfit_before', '')}",
        f"运行前继续价值：{(summary.get('judgement') or {}).get('continue_before', '')}",
        f"运行后过拟合：{(summary.get('judgement') or {}).get('overfit_after', '')}",
        f"运行后继续价值：{(summary.get('judgement') or {}).get('continue_after', '')}",
    ]
    return "\n".join(lines) + "\n"


def _should_send_email(summary: dict[str, Any], policy: str) -> bool:
    if policy == "never":
        return False
    if policy == "always":
        return True
    return str(summary.get("automation_status")) in {
        "monthly_ai_pool_updated",
        "monthly_ai_pool_update_blocked",
        "monthly_ai_pool_update_needed",
        "monthly_ai_pool_exception",
        "monthly_ai_pool_locked",
    }


def _send_email_if_needed(summary: dict[str, Any], report: str, paths: dict[str, Path], policy: str) -> dict[str, Any]:
    if not _should_send_email(summary, policy):
        return {"email_status": "skipped_by_policy", "email_policy": policy}
    status = str(summary.get("automation_status") or "unknown")
    if status == "monthly_ai_pool_updated":
        subject_status = "已更新"
        severity = "info"
    elif status == "monthly_ai_pool_already_current":
        subject_status = "已是最新"
        severity = "info"
    else:
        subject_status = "需处理"
        severity = "warning"
    subject = (
        f"[C9/15w][AI池月更{subject_status}] "
        f"应为{summary.get('expected_eval_date', '')} 当前{summary.get('current_eval_date', '')}"
    )
    return send_official_live_email_notification(
        subject=subject,
        body=report,
        event_type="stage935_monthly_ai_pool_update",
        severity=severity,
        attachments=[paths["summary_json"], paths["report_txt"]],
        metadata={
            "automation_status": status,
            "expected_eval_date": summary.get("expected_eval_date", ""),
            "current_eval_date": summary.get("current_eval_date", ""),
            "order_api_called_count": summary.get("order_api_called_count", 0),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live monthly AI pool auto updater.")
    parser.add_argument("--mode", choices=["check", "run"], default="run")
    parser.add_argument("--as-of", default="")
    parser.add_argument("--data-ready-time", default="16:30")
    parser.add_argument("--source-prefix", default=DEFAULT_SOURCE_PREFIX)
    parser.add_argument("--skip-data-update", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--email-policy", choices=["changes", "always", "never"], default="changes")
    parser.add_argument("--data-update-timeout-seconds", type=int, default=3600)
    parser.add_argument("--source-refresh-timeout-seconds", type=int, default=7200)
    parser.add_argument("--inference-timeout-seconds", type=int, default=3600)
    parser.add_argument("--disable-lock", action="store_true")
    args = parser.parse_args()

    CONTROL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    with _stage935_lock(enabled=not bool(args.disable_lock)) as lock_result:
        if lock_result.get("lock_status") == "lock_busy":
            summary = {
                "model_tag": MODEL_TAG,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "mode": str(args.mode),
                "automation_status": "monthly_ai_pool_locked",
                "action": "blocked_fail_closed_another_stage935_running",
                "blockers": ["stage935_lock_busy"],
                "warnings": [],
                "lock": lock_result,
                "order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "real_order_enabled": False,
            }
        else:
            try:
                summary = _run(args)
                summary["lock"] = lock_result
            except Exception as exc:
                summary = {
                    "model_tag": MODEL_TAG,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "official_live_version": OFFICIAL_LIVE_VERSION,
                    "official_live_alias": OFFICIAL_LIVE_ALIAS,
                    "mode": str(args.mode),
                    "automation_status": "monthly_ai_pool_exception",
                    "action": "exception_fail_closed",
                    "blockers": ["stage935_exception"],
                    "warnings": [],
                    "lock": lock_result,
                    "error": repr(exc),
                    "order_api_called_count": 0,
                    "cancel_order_api_called_count": 0,
                    "real_order_enabled": False,
                }

    report = _build_report(summary)
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_txt"].write_text(report, encoding="utf-8")
    paths["latest_summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["latest_report_txt"].write_text(report, encoding="utf-8")
    email_result = _send_email_if_needed(summary, report, paths, str(args.email_policy))
    summary["email_result"] = email_result
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["latest_summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(_exit_code_for_status(str(summary.get("automation_status", ""))))


if __name__ == "__main__":
    main()
