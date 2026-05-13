from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage249_phaseb_submit_adapter_v1"
APPROVAL_TAG = "stage243_phaseb_approval_v1"
APPROVAL_PREFIX = "qmt_roll_stage243_phaseb_approval"
CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_REAL_ORDERS"


def _paths(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "approval_csv": OUTPUT_DIR / f"{APPROVAL_PREFIX}_ledger_{date_key}_{APPROVAL_TAG}.csv",
        "result_csv": OUTPUT_DIR / f"qmt_roll_stage249_phaseb_submit_adapter_results_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"qmt_roll_stage249_phaseb_submit_adapter_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"qmt_roll_stage249_phaseb_submit_adapter_report_{date_key}_{MODEL_TAG}.md",
    }


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _to_int_flag(value: Any) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return 0
    return 1 if int(number) == 1 else 0


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def _submit_decision(row: dict[str, Any], requested_mode: str, real_enabled: bool, confirm_text: str) -> dict[str, Any]:
    reasons: list[str] = []
    status = "dry_run_ready"
    submit_api_called = 0
    broker_order_id = ""

    if _clean_scalar(row.get("approval_status")) != "approved_waiting_precheck":
        status = "blocked"
        reasons.append("approval_status_not_ready")

    if _to_int_flag(row.get("allow_real_new_orders")) != 1:
        status = "blocked"
        reasons.append("deployment_gate_blocked")

    if _to_int_flag(row.get("final_can_submit")) != 1:
        status = "blocked"
        reasons.append("final_gate_not_passed")

    if _clean_scalar(row.get("submit_status")) not in {"", "not_submitted"}:
        status = "blocked"
        reasons.append(f"submit_status={_clean_scalar(row.get('submit_status'))}")

    if requested_mode == "real":
        if not real_enabled:
            status = "blocked"
            reasons.append("phaseb_real_order_env_disabled")
        if confirm_text != CONFIRM_TEXT:
            status = "blocked"
            reasons.append("real_submit_confirmation_missing")
        if not reasons:
            status = "blocked"
            reasons.append("real_submit_adapter_not_implemented")

    return {
        "trade_date": row.get("trade_date", ""),
        "intent_id": row.get("intent_id", ""),
        "requested_mode": requested_mode,
        "submit_adapter_status": status,
        "submit_adapter_reason": ";".join(reasons),
        "submit_api_called": submit_api_called,
        "broker_order_id": broker_order_id,
        "vt_symbol": row.get("vt_symbol", ""),
        "direction": row.get("direction", ""),
        "offset": row.get("offset", ""),
        "planned_volume": row.get("planned_volume", ""),
        "draft_order_price": row.get("draft_order_price", ""),
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase B submit adapter with dry-run first safety switch.")
    parser.add_argument("--trade-date", required=True, help="Trade date, YYYY-MM-DD.")
    parser.add_argument("--mode", choices=["dry-run", "real"], default="dry-run")
    parser.add_argument("--confirm-real-submit", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.trade_date)
    approval = pd.read_csv(paths["approval_csv"], encoding="utf-8-sig")

    for column in [
        "submit_adapter_status",
        "submit_adapter_reason",
        "submit_adapter_checked_at",
        "submit_api_called",
        "broker_order_id",
        "submit_status",
    ]:
        if column not in approval.columns:
            approval[column] = ""
        approval[column] = approval[column].fillna("").astype(str)

    real_enabled = _env_enabled("PHASEB_REAL_ORDER_ENABLED")
    candidates = approval[approval["approval_status"].astype(str).eq("approved_waiting_precheck")].copy()
    results = pd.DataFrame(
        [
            _submit_decision(row, args.mode, real_enabled, args.confirm_real_submit)
            for row in candidates.to_dict(orient="records")
        ]
    )

    for row in results.to_dict(orient="records"):
        mask = approval["intent_id"].astype(str).eq(str(row["intent_id"]))
        approval.loc[mask, "submit_adapter_status"] = row["submit_adapter_status"]
        approval.loc[mask, "submit_adapter_reason"] = row["submit_adapter_reason"]
        approval.loc[mask, "submit_adapter_checked_at"] = row["checked_at"]
        approval.loc[mask, "submit_api_called"] = str(row["submit_api_called"])
        if row["broker_order_id"]:
            approval.loc[mask, "broker_order_id"] = row["broker_order_id"]

    approval.to_csv(paths["approval_csv"], index=False, encoding="utf-8-sig")
    results.to_csv(paths["result_csv"], index=False, encoding="utf-8-sig")

    if results.empty:
        ready_count = 0
        blocked_count = 0
        api_called_count = 0
    else:
        ready_count = int(results["submit_adapter_status"].astype(str).eq("dry_run_ready").sum())
        blocked_count = int(results["submit_adapter_status"].astype(str).eq("blocked").sum())
        api_called_count = int(pd.to_numeric(results["submit_api_called"], errors="coerce").fillna(0).sum())

    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": args.trade_date,
        "requested_mode": args.mode,
        "phaseb_real_order_env_enabled": real_enabled,
        "checked_intent_count": int(len(results)),
        "dry_run_ready_count": ready_count,
        "blocked_count": blocked_count,
        "submit_api_called_count": api_called_count,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。submit adapter 是执行安全层，不改策略信号或参数。",
            "continue_before": "是。即使 final_can_submit=1，也必须有最后一层默认不下单的保险。",
            "overfit_after": "否。dry-run 只记录可提交状态，不影响回测收益。",
            "continue_after": "是。下一步若要真实 submit，必须实现真实 broker adapter 并保留双重显式开关。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    report_lines = [
        "# Stage249 Phase B Submit Adapter",
        "",
        f"- 交易日：`{args.trade_date}`",
        f"- 请求模式：`{args.mode}`",
        f"- 真实下单环境开关：`{real_enabled}`",
        f"- submit API 调用次数：`{api_called_count}`",
        "",
        "## 结果",
        "",
        _to_markdown(
            results,
            [
                "intent_id",
                "requested_mode",
                "submit_adapter_status",
                "submit_adapter_reason",
                "submit_api_called",
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "draft_order_price",
                "checked_at",
            ],
        ),
        "",
        "## 说明",
        "",
        "- 默认 `dry-run` 只证明当前委托已经过最终闸门，不调用真实下单 API。",
        "- `real` 模式必须同时满足 `PHASEB_REAL_ORDER_ENABLED=1` 和命令行确认文本；当前真实 submit adapter 尚未实现，仍会阻断。",
        "- 真实 submit 实现前，`broker_order_id` 不会写入。",
        "",
    ]
    paths["report_md"].write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
