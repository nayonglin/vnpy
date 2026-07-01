from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage160_current_live_logic_healthcheck as s160
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage162"
MODEL_TAG = "stage162_official_live_pre_shadow_health_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage162_official_live_pre_shadow_health_gate"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s160._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s160._md_table(frame, max_rows=max_rows)


def _load_stage160_decision() -> dict[str, Any]:
    if not s160.DECISION_PATH.exists():
        raise FileNotFoundError(f"missing Stage160 decision: {s160.DECISION_PATH}")
    return json.loads(s160.DECISION_PATH.read_text(encoding="utf-8"))


def _load_stage160_checks() -> pd.DataFrame:
    if not s160.CHECKS_PATH.exists():
        raise FileNotFoundError(f"missing Stage160 checks: {s160.CHECKS_PATH}")
    return pd.read_csv(s160.CHECKS_PATH, encoding="utf-8-sig")


def _write_report(summary: dict[str, Any], checks: pd.DataFrame) -> None:
    view_cols = ["check_id", "status", "severity", "detail"]
    lines = [
        "# Stage162 Official Live Pre-Shadow Health Gate",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- 性质：只读 health gate；不连接 CTP，不调用订单 API。",
        "",
        "## Gate",
        "",
        f"- gate_status：`{summary['gate_status']}`",
        f"- exit_code：`{summary['exit_code']}`",
        f"- fail_count：`{summary['fail_count']}`",
        f"- warn_count：`{summary['warn_count']}`",
        f"- fail_on_warn：`{summary['fail_on_warn']}`",
        "",
        "## Stage160 Checks",
        "",
        _md_table(checks[view_cols], max_rows=80),
        "",
        "## Outputs",
        "",
        f"- stage160_checks：`{s160.CHECKS_PATH}`",
        f"- stage160_decision：`{s160.DECISION_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- report：`{REPORT_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the official-live pre-shadow read-only health gate.")
    parser.add_argument(
        "--skip-run-stage160",
        action="store_true",
        help="Reuse the latest Stage160 output instead of running the healthcheck first.",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Treat Stage160 WARN rows as blocking. Default only blocks FAIL rows.",
    )
    args = parser.parse_args()

    if not args.skip_run_stage160:
        s160.main()

    decision = _load_stage160_decision()
    checks = _load_stage160_checks()
    fail_rows = checks[checks["status"].astype(str).eq("FAIL")].copy()
    warn_rows = checks[checks["status"].astype(str).eq("WARN")].copy()

    blocking_rows = fail_rows
    if args.fail_on_warn:
        blocking_rows = pd.concat([blocking_rows, warn_rows], ignore_index=True)

    fail_count = int(len(fail_rows))
    warn_count = int(len(warn_rows))
    blocked = int(len(blocking_rows)) > 0
    gate_status = "blocked" if blocked else ("pass_with_warnings" if warn_count else "pass")
    exit_code = 2 if blocked else 0
    summary: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "gate_status": gate_status,
        "exit_code": exit_code,
        "fail_count": fail_count,
        "warn_count": warn_count,
        "fail_on_warn": bool(args.fail_on_warn),
        "blocking_checks": blocking_rows.to_dict(orient="records"),
        "stage160_decision": decision.get("decision", ""),
        "stage160_status_counts": decision.get("status_counts", {}),
        "stage160_outputs": decision.get("outputs", {}),
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": "否。Stage162 只是执行前 health gate，不改策略参数。",
        "continue_value_before": "是。当前风险集中在 profile/AI/order/pending/entry_context 漂移。",
        "overfit_reflection_after": "否。gate 结果只决定是否允许继续 shadow，不反馈到 alpha。",
        "continue_value_after": (
            "是。该 gate 可作为每日 shadow 或临时信号检查前的固定前置条件；WARN 需要工程排期，FAIL 必须阻断。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "stage160_checks": str(s160.CHECKS_PATH),
            "stage160_decision": str(s160.DECISION_PATH),
        },
    }

    SUMMARY_PATH.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, checks)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
