from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_execution_profile import (
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    assert_profile_identity,
    resolve_execution_profile,
)
from qmt_roll_official_pending_artifact import (
    load_validated_artifact_snapshot,
    materialize_validated_artifact_snapshot,
)
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_FAMILY_VERSION,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    build_official_live_manifest,
    build_official_live_risk_snapshot,
)
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_LIVE_REAL_POLICY_ENABLED_VALUE,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    READONLY_SUMMARY_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _parse_generated_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_seconds(value: Any) -> float | None:
    generated_dt = _parse_generated_at(value)
    if generated_dt is None:
        return None
    current_dt = (
        datetime.now(tz=generated_dt.tzinfo)
        if generated_dt.tzinfo is not None
        else datetime.now()
    )
    return round((current_dt - generated_dt).total_seconds(), 3)


def _readonly_snapshot_age_ready(
    age_seconds: float | None,
    *,
    max_snapshot_age_seconds: float,
) -> bool:
    return bool(
        age_seconds is not None
        and 0 <= age_seconds <= max_snapshot_age_seconds
    )


def _target_age_days(target_date: str) -> int | None:
    try:
        return (date.today() - datetime.strptime(target_date, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def _current_phase_d_sessions() -> list[dict[str, str]]:
    config = build_phase_d_config()
    now = datetime.now().time()
    active: list[dict[str, str]] = []
    for session in config.sessions:
        start_h, start_m = [int(part) for part in session.start.split(":", 1)]
        end_h, end_m = [int(part) for part in session.end.split(":", 1)]
        start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        in_session = start <= now <= end if start <= end else now >= start or now <= end
        if in_session:
            active.append({"name": session.name, "role": session.role})
    return active


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _stage260_binding_error(
    summary: dict[str, Any],
    *,
    profile: OfficialExecutionProfile,
    target_date: str,
    pending_cohort_id: str,
) -> str:
    if not summary or summary.get("_read_error"):
        return "stage260_summary_missing_or_unreadable"
    if _to_int(summary.get("order_api_called_count"), -1) != 0:
        return "stage260_order_api_count_nonzero"
    if summary.get("execution_profile") != profile.profile_key:
        return "stage260_execution_profile_mismatch"
    try:
        assert_profile_identity(
            profile,
            official_version=summary.get("official_live_version"),
            capital=summary.get("capital"),
            capital_label=summary.get("capital_label"),
        )
    except (TypeError, ValueError) as exc:
        return str(exc)
    if summary.get("trade_date") != target_date:
        return "stage260_target_date_mismatch"
    if (
        not profile.intraday_stop_retry_enabled
        and (
            not pending_cohort_id
            or summary.get("pending_cohort_id") != pending_cohort_id
        )
    ):
        return "stage260_pending_cohort_mismatch"
    return ""


def _official_summary_identity_error(
    summary: dict[str, Any],
    *,
    profile: OfficialExecutionProfile,
) -> str:
    try:
        if summary.get("execution_profile") != profile.profile_key:
            raise ValueError("execution_profile_key_mismatch")
        assert_profile_identity(
            profile,
            official_version=summary.get("official_live_version"),
            capital=summary.get("capital"),
            capital_label=summary.get("capital_label"),
        )
    except (TypeError, ValueError) as exc:
        return str(exc)
    return ""


def _stage260_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"qmt_roll_stage260_official_live_daily_execution_gate_summary_{date_key}_stage260_official_live_daily_execution_gate_v1.json"


def _stage251_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"qmt_roll_stage251_phaseb_fresh_pre_submit_gate_summary_{date_key}_stage251_phaseb_fresh_pre_submit_gate_v1.json"


def _check(
    rows: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    severity: str,
    observed: Any,
    required: Any,
    blocker: str = "",
    note: str = "",
) -> None:
    rows.append(
        {
            "check": name,
            "passed": int(bool(passed)),
            "severity": severity,
            "observed": observed,
            "required": required,
            "blocker": "" if passed else blocker,
            "note": note,
        }
    )


def _latest_pending_or_signal_count(signal_plan: pd.DataFrame, pending_orders: pd.DataFrame) -> int:
    return int(len(signal_plan) + len(pending_orders))


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    return view.to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    blocking = checks[checks["passed"].eq(0) & checks["severity"].eq("block")]
    return "\n".join(
        [
            "# Stage902 Official Live Phase D Readiness Gate",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 请求模式：`{summary['requested_mode']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- 总状态：`{summary['overall_status']}`",
            f"- 可进入全自动真实报单：`{summary['ready_for_phase_d_real']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## 阻断项",
            "",
            _to_markdown(blocking, ["check", "observed", "required", "blocker", "note"], max_rows=80),
            "",
            "## 全部检查",
            "",
            _to_markdown(checks, ["check", "passed", "severity", "observed", "required", "blocker"], max_rows=120),
            "",
            "## 说明",
            "",
            "- 本脚本只做 Phase D readiness 判定，不连接 CTP，不调用 `send_order`，不调用 `cancel_order`。",
            "- `dry-run` 模式允许验证 D 级控制面，但不代表真实报单已放开。",
            "- `live-real` 模式必须同时通过策略、账户、执行、kill switch、实盘 adapter、盘中守护进程和显式确认闸门。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed readiness gate for official-live Phase D automation.")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.C9_15W.value,
    )
    parser.add_argument("--target-date", default="", help="Target completed trading day. Defaults to official summary analysis_end.")
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--max-target-date-age-days", type=int, default=4)
    parser.add_argument(
        "--legacy-stage251-policy",
        choices=["optional", "require"],
        default="optional",
        help=(
            "Stage251 is a legacy SimNow/broker-test fresh gate. "
            "Production live submit uses Stage907/260/905/931 gates by default."
        ),
    )
    parser.add_argument("--confirm-live-real", default="")
    args = parser.parse_args()
    profile = resolve_execution_profile(args.execution_profile)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    official_summary = _read_json(profile.summary_path)
    signal_plan = _read_csv_maybe(profile.signal_plan_path)
    current_positions = _read_csv_maybe(profile.current_positions_path)
    pending_orders = _read_csv_maybe(profile.pending_orders_path)
    pending_cohort_id = ""
    pending_cohort_error = ""
    if not profile.intraday_stop_retry_enabled:
        try:
            materialized = materialize_validated_artifact_snapshot(
                profile,
                load_validated_artifact_snapshot(profile),
            )
            official_summary = materialized.official_summary
            signal_plan = materialized.signal_plan
            current_positions = materialized.current_positions
            pending_orders = materialized.pending_orders
            pending_cohort_id = str(
                materialized.audit.get("cohort_id", "")
            )
        except (OSError, TypeError, ValueError) as exc:
            pending_cohort_error = str(exc)
    if profile.intraday_stop_retry_enabled:
        manifest = build_official_live_manifest()
    else:
        manifest = {
            "alias": profile.alias,
            "version": profile.official_version,
            "source_stage": profile.source_stage,
            "capital": profile.capital,
            "capital_label": profile.capital_label,
            "execution_policy": {
                "real_submit_default": "fail_closed",
            },
        }
    target_date = args.target_date or str(official_summary.get("analysis_end", ""))
    paths = _paths(target_date)

    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    stage260_summary = _read_json(_stage260_summary_path(target_date))
    stage251_summary = _read_json(_stage251_summary_path(target_date))
    kill_switch = _read_json(KILL_SWITCH_PATH)

    official_identity_error = _official_summary_identity_error(
        official_summary,
        profile=profile,
    )

    risk_snapshot = build_official_live_risk_snapshot(official_summary)
    execution_policy = manifest.get("execution_policy", {})
    signal_or_pending_count = _latest_pending_or_signal_count(signal_plan, pending_orders)
    target_age_days = _target_age_days(target_date)
    current_phase_d_sessions = _current_phase_d_sessions()
    in_execution_session = any(row.get("role") == "market_and_execution" for row in current_phase_d_sessions)

    readonly_generated_at = readonly_summary.get("generated_at", "")
    readonly_age = _age_seconds(readonly_generated_at)
    broker_snapshot = readonly_summary.get("broker_snapshot", {}) if isinstance(readonly_summary.get("broker_snapshot"), dict) else {}
    position_state = str(broker_snapshot.get("position_snapshot_state", ""))
    readonly_ready = (
        readonly_summary.get("status") == "readonly_snapshots_received"
        and position_state in {"confirmed_flat", "positions_received"}
        and _readonly_snapshot_age_ready(
            readonly_age,
            max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        )
    )

    stage260_executable_count = _to_int(stage260_summary.get("executable_count"), 0)
    stage260_order_api_called = _to_int(stage260_summary.get("order_api_called_count"), 0)
    stage260_binding_error = _stage260_binding_error(
        stage260_summary,
        profile=profile,
        target_date=target_date,
        pending_cohort_id=pending_cohort_id,
    )
    stage251_status = str(stage251_summary.get("overall_status", ""))
    stage251_order_api_called = _to_int(stage251_summary.get("total_order_api_called_count"), 0)
    stage251_required = args.legacy_stage251_policy == "require" and stage260_executable_count > 0
    stage251_gate_satisfied = (
        stage260_executable_count == 0
        or stage251_status == "fresh_pre_submit_gate_passed"
        or args.legacy_stage251_policy == "optional"
    )
    stage251_clean = stage251_order_api_called == 0 and stage251_gate_satisfied

    live_real_env = _env_enabled(PHASE_D_REAL_ENABLED_ENV)
    session_daemon_env = _env_enabled(PHASE_D_SESSION_DAEMON_ENV)
    real_adapter_env = _env_enabled(PHASE_D_REAL_ADAPTER_ENV)
    confirm_ok = args.confirm_live_real == PHASE_D_CONFIRM_TEXT
    real_submit_policy = str(execution_policy.get("real_submit_default", ""))
    policy_live_real_enabled = real_submit_policy == PHASE_D_LIVE_REAL_POLICY_ENABLED_VALUE
    kill_switch_active = bool(kill_switch.get("enabled", False) or kill_switch.get("kill_switch_active", False))
    risk_level = str(risk_snapshot.get("risk_level", ""))
    allow_new_open = int(risk_level == "normal" and _to_int(risk_snapshot.get("allow_real_new_orders"), 0) == 1)
    allow_reduce_close = int(risk_level in {"normal", "review"})

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="official_execution_profile_resolved",
        passed=(
            profile.official_version
            in {
                "official_live_stage372_20w_recovery_sleeve",
                "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
            }
            and (
                not profile.intraday_stop_retry_enabled
                or OFFICIAL_LIVE_FAMILY_VERSION
                == "stage819_c9_intraday_stop_retry"
            )
        ),
        severity="block",
        observed=f"{profile.profile_key}/{profile.official_version}",
        required="registered Stage372 daily-only or explicit historical C9 profile",
        blocker="official_execution_profile_unregistered",
    )
    _check(
        checks,
        name="official_shadow_summary_available",
        passed=bool(official_summary.get("analysis_end"))
        and not official_summary.get("_read_error")
        and not official_identity_error,
        severity="block",
        observed=(
            official_identity_error
            or official_summary.get("analysis_end", "")
        ),
        required="latest official shadow decision json with exact profile identity",
        blocker="official_shadow_summary_missing_or_unreadable",
    )
    _check(
        checks,
        name="target_date_matches_shadow",
        passed=bool(target_date)
        and str(official_summary.get("analysis_end", "")) == target_date
        and (
            not profile.intraday_stop_retry_enabled
            or str(official_summary.get("analysis_start", ""))
            == OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE
        ),
        severity="block",
        observed=f"start={official_summary.get('analysis_start', '')};end={official_summary.get('analysis_end', '')}",
        required=(
            f"end={target_date}"
            if not profile.intraday_stop_retry_enabled
            else f"start={OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE};end={target_date}"
        ),
        blocker="target_date_not_equal_official_shadow_analysis_end",
    )
    _check(
        checks,
        name="live_real_execution_session",
        passed=args.mode != "live-real" or in_execution_session,
        severity="block",
        observed=current_phase_d_sessions,
        required="active Phase D market_and_execution session when --mode live-real",
        blocker="live_real_not_in_execution_session",
    )
    _check(
        checks,
        name="live_real_target_date_not_stale",
        passed=args.mode != "live-real"
        or (target_age_days is not None and 0 <= target_age_days <= args.max_target_date_age_days),
        severity="block",
        observed=target_age_days,
        required=f"0 <= target age days <= {args.max_target_date_age_days} when --mode live-real",
        blocker="live_real_target_date_stale_or_invalid",
    )
    _check(
        checks,
        name="official_risk_allows_new_orders",
        passed=allow_new_open == 1,
        severity="block",
        observed=f"{risk_level} / allow_new_open={allow_new_open} / allow_reduce_close={allow_reduce_close}",
        required="normal / allow=1",
        blocker="official_risk_state_blocks_new_open",
        note="review 状态只能降风险，不能自动新增开仓。",
    )
    _check(
        checks,
        name="official_risk_allows_reduce_close",
        passed=allow_reduce_close == 1,
        severity="info" if allow_reduce_close else "block",
        observed=f"{risk_level} / allow_reduce_close={allow_reduce_close}",
        required="normal or review allows broker-matched close/reduce",
        blocker="official_risk_state_blocks_reduce_close",
    )
    _check(
        checks,
        name="signal_and_pending_exports_available",
        passed=(
            profile.signal_plan_path.exists()
            and profile.pending_orders_path.exists()
            and (
                profile.intraday_stop_retry_enabled
                or not pending_cohort_error
            )
        ),
        severity="block",
        observed=(
            f"signal={len(signal_plan)} pending={len(pending_orders)} "
            f"positions={len(current_positions)} cohort={pending_cohort_id} "
            f"cohort_error={pending_cohort_error}"
        ),
        required=(
            "Stage372 signal_plan and pending_orders csv"
            if not profile.intraday_stop_retry_enabled
            else "signal_plan and pending_orders csv"
        ),
        blocker="signal_or_pending_export_missing",
    )
    _check(
        checks,
        name="broker_readonly_snapshot_fresh",
        passed=readonly_ready,
        severity="block",
        observed=f"status={readonly_summary.get('status', '')};state={position_state};age={readonly_age}",
        required=f"readonly_snapshots_received and age<={args.max_snapshot_age_seconds}s",
        blocker="broker_snapshot_missing_stale_or_ambiguous",
    )
    _check(
        checks,
        name="stage260_execution_gate_available",
        passed=not stage260_binding_error,
        severity="block",
        observed=(
            f"exists={bool(stage260_summary)} executable={stage260_executable_count} "
            f"order_api={stage260_order_api_called} "
            f"profile={stage260_summary.get('execution_profile', '')} "
            f"date={stage260_summary.get('trade_date', '')} "
            f"cohort={stage260_summary.get('pending_cohort_id', '')} "
            f"binding_error={stage260_binding_error}"
        ),
        required="fresh profile/date/cohort-bound Stage260 execution gate with order_api=0",
        blocker="stage260_gate_missing_or_order_api_called",
    )
    _check(
        checks,
        name="stage251_fresh_pre_submit_gate_when_executable",
        passed=stage251_clean,
        severity="block" if stage251_required or stage251_order_api_called != 0 else "info",
        observed=(
            f"stage260_executable={stage260_executable_count};"
            f"stage251={stage251_status};order_api={stage251_order_api_called};"
            f"legacy_policy={args.legacy_stage251_policy}"
        ),
        required="Stage251 passed only when legacy policy=require; always order_api=0",
        blocker="fresh_pre_submit_gate_missing_or_blocked",
        note=(
            "当前生产实盘开仓以前置只读快照、Stage260、Stage905、Stage931 最终报单前校验为准；"
            "Stage251 仍保留给 SimNow/broker-test 或显式 legacy 验收。"
        ),
    )
    _check(
        checks,
        name="kill_switch_clear",
        passed=not kill_switch_active,
        severity="block",
        observed=f"active={kill_switch_active};path={KILL_SWITCH_PATH}",
        required="kill switch absent or inactive",
        blocker="phase_d_kill_switch_active",
    )
    _check(
        checks,
        name="c9_intraday_session_daemon_enabled",
        passed=(
            session_daemon_env
            if profile.intraday_stop_retry_enabled
            else True
        ),
        severity="block" if profile.intraday_stop_retry_enabled else "info",
        observed=f"{PHASE_D_SESSION_DAEMON_ENV}={os.getenv(PHASE_D_SESSION_DAEMON_ENV, '')}",
        required=(
            f"{PHASE_D_SESSION_DAEMON_ENV}=1"
            if profile.intraday_stop_retry_enabled
            else "not applicable for Stage372 daily-only profile"
        ),
        blocker="entry_day_05r_stop_retry_requires_session_daemon",
        note="C9 的 0.5R 止损/重试不是日终 cron 能完成的职责。",
    )
    _check(
        checks,
        name="strategy_real_submit_adapter_implemented",
        passed=real_adapter_env,
        severity="block",
        observed=f"{PHASE_D_REAL_ADAPTER_ENV}={os.getenv(PHASE_D_REAL_ADAPTER_ENV, '')}",
        required=f"{PHASE_D_REAL_ADAPTER_ENV}=1 after code review and smoke evidence",
        blocker="official_strategy_real_submit_adapter_not_enabled",
    )
    _check(
        checks,
        name="real_submit_policy_explicit_live_real_enabled",
        passed=args.mode == "dry-run" or policy_live_real_enabled,
        severity="block",
        observed=real_submit_policy,
        required=f"{PHASE_D_LIVE_REAL_POLICY_ENABLED_VALUE} when --mode live-real",
        blocker="official_live_config_real_submit_policy_not_explicitly_enabled",
    )
    _check(
        checks,
        name="live_real_explicit_enable_and_confirmation",
        passed=args.mode == "dry-run" or (live_real_env and confirm_ok),
        severity="block",
        observed=f"mode={args.mode};{PHASE_D_REAL_ENABLED_ENV}={os.getenv(PHASE_D_REAL_ENABLED_ENV, '')};confirm_ok={confirm_ok}",
        required=f"live-real requires {PHASE_D_REAL_ENABLED_ENV}=1 and exact confirm text",
        blocker="live_real_env_or_confirmation_missing",
    )
    _check(
        checks,
        name="hard_limits_declared",
        passed=True,
        severity="info",
        observed="max_order_count_per_cycle=3; max_snapshot_age_seconds=300; close_requires_matching_broker_position; active_orders_block_new_submit",
        required="declared hard execution limits",
        note="Stage902 only declares/evaluates readiness; actual daemon must enforce the same limits before every submit.",
    )
    _check(
        checks,
        name="no_order_api_called_by_stage902",
        passed=True,
        severity="info",
        observed=0,
        required=0,
    )

    checks_df = pd.DataFrame(checks)
    blocking_failures = checks_df[checks_df["passed"].eq(0) & checks_df["severity"].eq("block")]
    if allow_reduce_close:
        reduce_close_blocking_failures = blocking_failures[
            ~blocking_failures["check"].eq("official_risk_allows_new_orders")
        ]
    else:
        reduce_close_blocking_failures = blocking_failures
    ready_for_phase_d_real = int(args.mode == "live-real" and blocking_failures.empty)
    overall_status = "phase_d_ready_for_live_real" if ready_for_phase_d_real else "phase_d_blocked"
    if args.mode == "dry-run" and blocking_failures.empty:
        overall_status = "phase_d_readiness_dry_run_passed_real_still_disabled"

    order_api_called = stage260_order_api_called + stage251_order_api_called
    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "requested_mode": args.mode,
        "target_date": target_date,
        "execution_profile": profile.profile_key,
        "official_live_version": profile.official_version,
        "official_live_alias": profile.alias,
        "capital": profile.capital,
        "capital_label": profile.capital_label,
        "intraday_stop_retry_enabled": int(
            profile.intraday_stop_retry_enabled
        ),
        "official_manifest": manifest,
        "risk_snapshot": risk_snapshot,
        "allow_new_open": allow_new_open,
        "allow_reduce_close": allow_reduce_close,
        "signal_count": int(len(signal_plan)),
        "pending_order_count": int(len(pending_orders)),
        "pending_cohort_id": pending_cohort_id,
        "pending_cohort_error": pending_cohort_error,
        "signal_or_pending_count": signal_or_pending_count,
        "current_position_count": int(len(current_positions)),
        "readonly_snapshot_age_seconds": readonly_age,
        "target_date_age_days": target_age_days,
        "current_phase_d_sessions": current_phase_d_sessions,
        "stage260_executable_count": stage260_executable_count,
        "stage260_order_api_called_count": stage260_order_api_called,
        "stage251_status": stage251_status,
        "legacy_stage251_policy": args.legacy_stage251_policy,
        "stage251_required": int(stage251_required),
        "stage251_order_api_called_count": stage251_order_api_called,
        "order_api_called_count": order_api_called,
        "ready_for_phase_d_real": ready_for_phase_d_real,
        "overall_status": overall_status,
        "blocking_failure_count": int(len(blocking_failures)),
        "blocking_failures": blocking_failures.to_dict(orient="records"),
        "blocking_failure_count_for_reduce_close": int(len(reduce_close_blocking_failures)),
        "blocking_failures_for_reduce_close": reduce_close_blocking_failures.to_dict(orient="records"),
        "kill_switch_path": str(KILL_SWITCH_PATH.resolve()),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "external_research_conclusion": (
                "FCA/CFTC materials emphasize effective systems, thresholds, erroneous-order prevention, "
                "business continuity, pre-trade controls, and post-trade risk reconciliation; this supports "
                "building Phase D controls but not bypassing fail-closed gates."
            ),
            "overfit_before": "否。Phase D readiness gate 是执行工程与风控闸门，不改 C9 策略参数或历史样本。",
            "continue_before": "是。用户希望直接到 D，当前最有价值的是先证明哪些 D 级硬闸门缺失。",
            "overfit_after": "否。脚本只读配置、影子产物和执行快照，不根据结果调整策略。",
            "continue_after": (
                "是，但必须先补齐盘中守护进程、真实策略 submit adapter、fresh broker-state gate、"
                "kill switch 和对账闭环；在这些失败前不应打开真实自动报单。"
            ),
        },
    }

    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
