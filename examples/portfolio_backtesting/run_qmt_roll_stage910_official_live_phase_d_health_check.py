from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import (
    CONTROLLER_HEARTBEAT_PATH,
    CONTROLLER_STATE_PATH,
    KILL_SWITCH_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage910_official_live_phase_d_health_check_v1"
OUTPUT_PREFIX = "qmt_roll_stage910_official_live_phase_d_health_check"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{run_id}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
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
    dt = _parse_dt(value)
    if dt is None:
        return None
    return round((datetime.now() - dt).total_seconds(), 3)


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
    return df.loc[:, [column for column in columns if column in df.columns]].head(80).to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame) -> str:
    blocking = checks[checks["severity"].eq("block") & checks["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage910 Official Live Phase D Health Check",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- health 状态：`{summary['health_status']}`",
            f"- controller 状态：`{summary['controller_status']}`",
            f"- heartbeat age seconds：`{summary['heartbeat_age_seconds']}`",
            f"- kill switch active：`{summary['kill_switch_active']}`",
            "",
            "## Blocking Checks",
            "",
            _to_markdown(blocking, ["check", "observed", "required", "blocker"]),
            "",
            "## 说明",
            "",
            "- Stage910 只检查后台控制器心跳、state 和 kill switch，不连接 CTP，不提交委托。",
            "- `controller_alive_fail_closed` 表示守护进程活着，但交易闸门仍处于 fail-closed。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D health check.")
    parser.add_argument("--max-heartbeat-age-seconds", type=int, default=0)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    config = build_phase_d_config()
    max_age = args.max_heartbeat_age_seconds or config.hard_limits.max_heartbeat_age_seconds
    heartbeat = _read_json(CONTROLLER_HEARTBEAT_PATH)
    state = _read_json(CONTROLLER_STATE_PATH)
    kill_switch = _read_json(KILL_SWITCH_PATH)
    heartbeat_age = _age_seconds(heartbeat.get("heartbeat_at"))
    heartbeat_fresh = heartbeat_age is not None and heartbeat_age <= max_age
    controller_status = _clean(heartbeat.get("controller_status") or state.get("controller_status"))
    kill_active = bool(kill_switch.get("enabled", False) or kill_switch.get("kill_switch_active", False))
    order_api_called = int(pd.to_numeric(heartbeat.get("order_api_called_count", 0), errors="coerce") or 0)

    checks: list[dict[str, Any]] = []
    _check_row(
        checks,
        check="heartbeat_file_present_and_fresh",
        passed=heartbeat_fresh,
        severity="block",
        observed=f"path={CONTROLLER_HEARTBEAT_PATH};age={heartbeat_age}",
        required=f"age<={max_age}s",
        blocker="controller_heartbeat_missing_or_stale",
    )
    _check_row(
        checks,
        check="controller_state_present",
        passed=bool(state) and not state.get("_read_error"),
        severity="block",
        observed=str(CONTROLLER_STATE_PATH),
        required="controller state json readable",
        blocker="controller_state_missing_or_unreadable",
    )
    _check_row(
        checks,
        check="kill_switch_clear",
        passed=not kill_active,
        severity="block",
        observed=f"active={kill_active};path={KILL_SWITCH_PATH}",
        required="kill switch inactive",
        blocker="kill_switch_active",
    )
    _check_row(
        checks,
        check="controller_order_api_zero",
        passed=order_api_called == 0,
        severity="block",
        observed=order_api_called,
        required=0,
        blocker="controller_order_api_called",
    )
    checks_df = pd.DataFrame(checks)
    blocking = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]
    if not blocking.empty:
        health_status = "controller_health_blocked"
    elif "ready" in controller_status:
        health_status = "controller_alive_ready"
    else:
        health_status = "controller_alive_fail_closed"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "health_status": health_status,
        "controller_status": controller_status,
        "heartbeat_age_seconds": heartbeat_age,
        "kill_switch_active": kill_active,
        "order_api_called_count": order_api_called,
        "blocking_failure_count": int(len(blocking)),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。health check 是运行监控，不改策略。",
            "continue_before": "是。全自动必须能监控后台心跳。",
            "overfit_after": "否。监控结果只影响运维状态。",
            "continue_after": "是。下一步应在 launchd/监控中周期运行该 health check。",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
