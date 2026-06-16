from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage908_official_live_submit_adapter_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage908_official_live_submit_adapter_contract"
STAGE902_MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
STAGE902_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE906_MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
STAGE906_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "checks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{date_key}_{MODEL_TAG}.csv",
        "submit_batch_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_submit_batch_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage902_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE902_PREFIX}_summary_{date_key}_{STAGE902_MODEL_TAG}.json"


def _stage905_intents_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_intents_{date_key}_{STAGE905_MODEL_TAG}.csv"


def _stage905_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_summary_{date_key}_{STAGE905_MODEL_TAG}.json"


def _stage906_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE906_PREFIX}_summary_{date_key}_{STAGE906_MODEL_TAG}.json"


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


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


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


def _ready_intents(intents: pd.DataFrame) -> pd.DataFrame:
    if intents.empty or "executor_status" not in intents.columns:
        return pd.DataFrame()
    return intents[intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")].copy()


def _build_submit_batch(ready_intents: pd.DataFrame, mode: str, checks_blocked: bool) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in ready_intents.to_dict(orient="records"):
        rows.append(
            {
                "adapter_batch_id": f"STAGE908-{len(rows) + 1:03d}",
                "intent_id": _clean(row.get("intent_id")),
                "vt_symbol": _clean(row.get("vt_symbol")),
                "direction": _clean(row.get("direction")),
                "offset": _clean(row.get("offset")),
                "volume": row.get("planned_volume", ""),
                "limit_price": row.get("limit_price", ""),
                "gateway_name": "CTP",
                "mode": mode,
                "adapter_contract_status": "blocked" if checks_blocked else "contract_ready_dry_run",
                "live_submit_permitted": 0,
                "live_submit_reason": "real broker adapter intentionally unavailable in Stage908",
                "order_api_called": 0,
            }
        )
    return pd.DataFrame(rows)


def _to_markdown(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(80).to_markdown(index=False)


def _build_report(summary: dict[str, Any], checks: pd.DataFrame, submit_batch: pd.DataFrame) -> str:
    blocking = checks[checks["severity"].eq("block") & checks["passed"].eq(0)]
    return "\n".join(
        [
            "# Stage908 Official Live Submit Adapter Contract",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- 请求模式：`{summary['mode']}`",
            f"- adapter 合约状态：`{summary['adapter_contract_status']}`",
            f"- live submit permitted：`{summary['live_submit_permitted']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Blocking Checks",
            "",
            _to_markdown(blocking, ["check", "observed", "required", "blocker"]),
            "",
            "## Submit Batch",
            "",
            _to_markdown(
                submit_batch,
                [
                    "adapter_batch_id",
                    "intent_id",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "volume",
                    "limit_price",
                    "adapter_contract_status",
                    "live_submit_permitted",
                    "live_submit_reason",
                ],
            ),
            "",
            "## 说明",
            "",
            "- Stage908 只是提交适配器合约审计，不连接 CTP，不提交委托。",
            "- 真实 adapter 必须在 Stage902、Stage905、Stage906、kill switch 和 env gate 全部通过后，才允许接入最后一层 broker 调用。",
            "- 当前 `live_submit_permitted=0` 是设计要求；它证明合约已定义，但真实 adapter 尚未启用。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live submit adapter contract audit.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--confirm-live-real", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    config = build_phase_d_config()
    stage902 = _read_json(_stage902_summary_path(args.target_date))
    stage905 = _read_json(_stage905_summary_path(args.target_date))
    stage906 = _read_json(_stage906_summary_path(args.target_date))
    intents = _read_csv_maybe(_stage905_intents_path(args.target_date))
    kill_switch = _read_json(KILL_SWITCH_PATH)
    ready_intents = _ready_intents(intents)
    real_adapter_enabled = _env_enabled(PHASE_D_REAL_ADAPTER_ENV)
    real_submit_enabled = _env_enabled(PHASE_D_REAL_ENABLED_ENV)
    confirm_ok = args.confirm_live_real == PHASE_D_CONFIRM_TEXT
    kill_active = bool(kill_switch.get("enabled", False) or kill_switch.get("kill_switch_active", False))
    no_action_idle = (
        len(ready_intents) == 0
        and stage905.get("executor_status") == "executor_no_intents"
        and stage906.get("reconciliation_status") == "reconcile_aligned"
        and stage902.get("overall_status")
        in {
            "phase_d_readiness_dry_run_passed_real_still_disabled",
            "phase_d_readiness_ready_for_real_submit",
        }
    )

    checks: list[dict[str, Any]] = []
    _check_row(
        checks,
        check="stage902_phase_d_real_ready",
        passed=_to_int(stage902.get("ready_for_phase_d_real"), 0) == 1 or no_action_idle,
        severity="block",
        observed=f"overall={stage902.get('overall_status', '')};ready={stage902.get('ready_for_phase_d_real', '')}",
        required="ready_for_phase_d_real=1, or reconciled no-action idle dry-run",
        blocker="phase_d_readiness_not_ready",
    )
    _check_row(
        checks,
        check="stage905_has_ready_intents",
        passed=(len(ready_intents) > 0 and _to_int(stage905.get("blocked_count"), 0) == 0) or no_action_idle,
        severity="block",
        observed=f"ready={len(ready_intents)};blocked={stage905.get('blocked_count', '')}",
        required="ready intents >0 and blocked_count=0, or reconciled no-action idle",
        blocker="executor_intents_not_ready",
    )
    _check_row(
        checks,
        check="stage906_account_reconciled",
        passed=stage906.get("reconciliation_status") == "reconcile_aligned",
        severity="block",
        observed=f"{stage906.get('reconciliation_status', '')};{stage906.get('account_state_alignment', '')}",
        required="reconcile_aligned",
        blocker="account_not_reconciled",
    )
    _check_row(
        checks,
        check="kill_switch_clear",
        passed=not kill_active,
        severity="block",
        observed=f"active={kill_active}",
        required="kill switch inactive",
        blocker="kill_switch_active",
    )
    _check_row(
        checks,
        check="real_adapter_env_enabled",
        passed=args.mode == "dry-run" or real_adapter_enabled,
        severity="block",
        observed=f"{PHASE_D_REAL_ADAPTER_ENV}={os.getenv(PHASE_D_REAL_ADAPTER_ENV, '')}",
        required=f"{PHASE_D_REAL_ADAPTER_ENV}=1 when live-real",
        blocker="real_adapter_env_missing",
    )
    _check_row(
        checks,
        check="real_submit_env_and_confirmation",
        passed=args.mode == "dry-run" or (real_submit_enabled and confirm_ok),
        severity="block",
        observed=f"{PHASE_D_REAL_ENABLED_ENV}={os.getenv(PHASE_D_REAL_ENABLED_ENV, '')};confirm_ok={confirm_ok}",
        required=f"{PHASE_D_REAL_ENABLED_ENV}=1 and exact confirm text when live-real",
        blocker="real_submit_env_or_confirmation_missing",
    )
    _check_row(
        checks,
        check="hard_limits_available",
        passed=True,
        severity="info",
        observed=json.dumps(config.hard_limits.__dict__, ensure_ascii=False, sort_keys=True),
        required="Phase D hard limits declared",
    )
    _check_row(
        checks,
        check="no_order_api_called_by_stage908",
        passed=True,
        severity="info",
        observed=0,
        required=0,
    )

    checks_df = pd.DataFrame(checks)
    blocking = checks_df[checks_df["severity"].eq("block") & checks_df["passed"].eq(0)]
    checks_blocked = not blocking.empty
    submit_batch = _build_submit_batch(ready_intents, args.mode, checks_blocked)
    if checks_blocked:
        adapter_status = "adapter_contract_blocked"
    elif no_action_idle:
        adapter_status = "adapter_contract_no_intents_idle"
    elif args.mode == "dry-run":
        adapter_status = "adapter_contract_ready_dry_run"
    else:
        adapter_status = "adapter_contract_ready_for_external_live_adapter_review"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "mode": args.mode,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "adapter_contract_status": adapter_status,
        "ready_intent_count": int(len(ready_intents)),
        "submit_batch_count": int(len(submit_batch)),
        "blocking_failure_count": int(len(blocking)),
        "live_submit_permitted": 0,
        "order_api_called_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage908 是执行接口合约审计，不改 C9 策略。",
            "continue_before": "是。全自动需要明确最后一层 adapter 的输入合同和阻断条件。",
            "overfit_after": "否。结果只影响执行是否放行。",
            "continue_after": "是。下一步应把 Stage908 接入 Stage903，并在 broker 快照/对账通过后做 live adapter code review。",
        },
    }
    checks_df.to_csv(paths["checks_csv"], index=False, encoding="utf-8-sig")
    submit_batch.to_csv(paths["submit_batch_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, checks_df, submit_batch), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
