from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage243_phaseb_approval_v1"
ORDER_DRAFT_TAG = "stage242_phaseb_order_draft_v1"
ORDER_DRAFT_PREFIX = "qmt_roll_stage242_phaseb_order_draft"
OUTPUT_PREFIX = "qmt_roll_stage243_phaseb_approval"


def _paths(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "draft_csv": OUTPUT_DIR / f"{ORDER_DRAFT_PREFIX}_draft_{date_key}_{ORDER_DRAFT_TAG}.csv",
        "approval_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_{date_key}_{MODEL_TAG}.csv",
        "events_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_or_init_ledger(trade_date: str, paths: dict[str, Path]) -> pd.DataFrame:
    ledger = _read_csv(paths["approval_csv"])
    if ledger.empty:
        draft = pd.read_csv(paths["draft_csv"], encoding="utf-8-sig")
        draft["approval_updated_at"] = ""
        ledger = draft
    string_columns = [
        "approval_status",
        "blocked_reason",
        "risk_level",
        "historical_first_sweep_date",
        "vt_symbol",
        "direction",
        "offset",
        "draft_price_source",
        "proxy_quality",
        "operator_action",
        "operator_id",
        "operator_note",
        "approved_at",
        "submit_mode",
        "pre_submit_check_status",
        "broker_order_id",
        "submit_status",
        "approval_updated_at",
    ]
    for column in string_columns:
        if column not in ledger.columns:
            ledger[column] = ""
        ledger[column] = ledger[column].fillna("").astype(str)
    return ledger


def _transition(current: str, action: str) -> str:
    if action == "approve":
        if current not in {"pending_manual_approval", "deferred"}:
            raise ValueError(f"cannot approve from state={current}")
        return "approved_waiting_precheck"
    if action == "reject":
        if current not in {"pending_manual_approval", "deferred"}:
            raise ValueError(f"cannot reject from state={current}")
        return "manually_rejected"
    if action == "defer":
        if current not in {"pending_manual_approval", "deferred"}:
            raise ValueError(f"cannot defer from state={current}")
        return "deferred"
    raise ValueError(f"unknown action={action}")


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase B manual approval state switcher.")
    parser.add_argument("--trade-date", required=True, help="Trade date, YYYY-MM-DD.")
    parser.add_argument("--intent-id", required=True, help="Intent id to update.")
    parser.add_argument("--action", required=True, choices=["approve", "reject", "defer"])
    parser.add_argument("--operator", default="manual_operator", help="Operator id.")
    parser.add_argument("--note", default="", help="Approval note.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.trade_date)
    ledger = _load_or_init_ledger(args.trade_date, paths)
    if ledger.empty:
        raise FileNotFoundError(f"missing draft ledger: {paths['draft_csv']}")

    mask = ledger["intent_id"].astype(str).eq(args.intent_id)
    if not mask.any():
        raise ValueError(f"intent_id not found: {args.intent_id}")

    idx = ledger.index[mask][0]
    current = str(ledger.at[idx, "approval_status"])
    if current == "blocked_by_gate":
        raise ValueError("blocked_by_gate intent cannot enter manual approval")

    next_status = _transition(current, args.action)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ledger.at[idx, "approval_status"] = next_status
    ledger.at[idx, "operator_action"] = args.action
    ledger.at[idx, "operator_id"] = args.operator
    ledger.at[idx, "operator_note"] = args.note
    ledger.at[idx, "approval_updated_at"] = now
    ledger.at[idx, "approved_at"] = now if args.action == "approve" else ""
    ledger.at[idx, "pre_submit_check_status"] = "pending" if args.action == "approve" else "not_run"

    previous_events = _read_csv(paths["events_csv"])
    event_row = pd.DataFrame(
        [
            {
                "trade_date": args.trade_date,
                "intent_id": args.intent_id,
                "previous_status": current,
                "action": args.action,
                "next_status": next_status,
                "operator_id": args.operator,
                "operator_note": args.note,
                "event_time": now,
            }
        ]
    )
    events = pd.concat([previous_events, event_row], ignore_index=True) if not previous_events.empty else event_row

    ledger.to_csv(paths["approval_csv"], index=False, encoding="utf-8-sig")
    events.to_csv(paths["events_csv"], index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": args.trade_date,
        "intent_id": args.intent_id,
        "action": args.action,
        "operator_id": args.operator,
        "updated_status": next_status,
        "approval_counts": ledger["approval_status"].value_counts(dropna=False).to_dict(),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Phase B 审批只是状态切换，不改策略信号或参数。",
            "continue_before": "是。没有审批动作，半自动执行无法闭环。",
            "overfit_after": "否。审批结果不会反向改动 signal_intent。",
            "continue_after": "是。下一步可以接 pre-submit check，但仍不应直接接真实 submit。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    report_lines = [
        "# Stage243 Phase B Approval",
        "",
        f"- 交易日：`{args.trade_date}`",
        f"- intent_id：`{args.intent_id}`",
        f"- 动作：`{args.action}`",
        f"- 操作人：`{args.operator}`",
        f"- 新状态：`{next_status}`",
        "",
        "## 当前审批账本",
        "",
        _to_markdown(
            ledger,
            [
                "intent_id",
                "approval_status",
                "operator_action",
                "operator_id",
                "operator_note",
                "approved_at",
                "pre_submit_check_status",
                "submit_status",
            ],
        ),
        "",
        "## 审批事件",
        "",
        _to_markdown(
            events.tail(10),
            [
                "event_time",
                "intent_id",
                "previous_status",
                "action",
                "next_status",
                "operator_id",
                "operator_note",
            ],
        ),
        "",
        "## 说明",
        "",
        "- 本阶段只更新审批状态，不触发真实下单。",
        "- `approved_waiting_precheck` 表示下一步应进入发单前二次校验。",
        "",
    ]
    paths["report_md"].write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
