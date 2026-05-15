from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage244_phaseb_pre_submit_check_v1"
APPROVAL_TAG = "stage243_phaseb_approval_v1"
APPROVAL_PREFIX = "qmt_roll_stage243_phaseb_approval"

READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"
READONLY_SUCCESS_STATUSES = {"connected_or_attempted_readonly", "readonly_snapshots_received"}
ACTIVE_ORDER_STATUSES = {
    "submitting",
    "submitted",
    "nottraded",
    "not traded",
    "parttraded",
    "part traded",
    "partial_filled",
    "提交中",
    "未成交",
    "部分成交",
}


def _paths(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "approval_csv": OUTPUT_DIR / f"{APPROVAL_PREFIX}_ledger_{date_key}_{APPROVAL_TAG}.csv",
        "result_csv": OUTPUT_DIR / f"qmt_roll_stage244_phaseb_pre_submit_check_results_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"qmt_roll_stage244_phaseb_pre_submit_check_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"qmt_roll_stage244_phaseb_pre_submit_check_report_{date_key}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def _has_error_logs(logs: pd.DataFrame) -> tuple[bool, str]:
    if logs.empty or "msg" not in logs.columns:
        return False, ""
    messages = logs["msg"].astype(str)
    for msg in messages:
        lower = msg.lower()
        if any(keyword in lower for keyword in ["失败", "错误", "不合法", "error", "failed", "reject"]):
            return True, msg
    return False, ""


def _column(df: pd.DataFrame, *candidates: str) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name]
    return pd.Series([""] * len(df), index=df.index)


def _latest_order_rows(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders
    latest = orders.copy().reset_index(drop=False).rename(columns={"index": "_event_index"})
    if "vt_orderid" in latest.columns:
        key = latest["vt_orderid"].fillna("").astype(str).str.strip()
    else:
        key = pd.Series([""] * len(latest), index=latest.index)
    if "gateway_name" in latest.columns and "orderid" in latest.columns:
        fallback = (
            latest["gateway_name"].fillna("").astype(str).str.strip()
            + "."
            + latest["orderid"].fillna("").astype(str).str.strip()
        )
    else:
        fallback = _column(latest, "orderid")
    latest["_order_key"] = key.where(key.ne(""), fallback)
    latest = latest.sort_values("_event_index").groupby("_order_key", as_index=False, dropna=False).tail(1)
    return latest.drop(columns=["_event_index", "_order_key"], errors="ignore")


def _build_result_row(row: dict[str, Any], readonly_summary: dict[str, Any], accounts: pd.DataFrame, positions: pd.DataFrame, orders: pd.DataFrame, logs: pd.DataFrame) -> dict[str, Any]:
    reasons: list[str] = []
    can_submit = True

    if str(row.get("approval_status", "")) != "approved_waiting_precheck":
        can_submit = False
        reasons.append("intent_not_approved_for_precheck")

    if int(pd.to_numeric(row.get("allow_real_new_orders"), errors="coerce") or 0) != 1:
        can_submit = False
        reasons.append("deployment_gate_blocked")

    readonly_status = str(readonly_summary.get("status", ""))
    if readonly_status not in READONLY_SUCCESS_STATUSES:
        can_submit = False
        reasons.append(f"readonly_probe_not_ready:{readonly_status or 'missing'}")

    if readonly_summary.get("missing_required_env"):
        can_submit = False
        reasons.append("missing_required_env")

    gateway_import = readonly_summary.get("gateway_import", {})
    if not gateway_import.get("ctp_gateway_import_available", False):
        can_submit = False
        reasons.append("ctp_gateway_unavailable")

    has_error_log, error_msg = _has_error_logs(logs)
    if has_error_log:
        can_submit = False
        reasons.append(f"log_error:{error_msg}")

    if accounts.empty:
        can_submit = False
        reasons.append("broker_account_snapshot_missing")

    # Empty positions means flat is possible; not a blocker by itself.

    live_open_orders = 0
    latest_orders = _latest_order_rows(orders)
    if not latest_orders.empty and "status" in latest_orders.columns:
        status_series = latest_orders["status"].fillna("").astype(str).str.strip().str.lower()
        live_open_orders = int(status_series.isin(ACTIVE_ORDER_STATUSES).sum())
    if live_open_orders > 0:
        can_submit = False
        reasons.append("existing_live_open_orders")

    status = "passed" if can_submit else "failed"
    return {
        "trade_date": row.get("trade_date", ""),
        "intent_id": row.get("intent_id", ""),
        "approval_status": row.get("approval_status", ""),
        "pre_submit_check_status": status,
        "can_submit": 1 if can_submit else 0,
        "failure_reason": ";".join(reasons),
        "readonly_probe_status": readonly_summary.get("status", ""),
        "gateway_import_ok": 1 if gateway_import.get("ctp_gateway_import_available", False) else 0,
        "broker_account_rows": int(len(accounts)),
        "broker_position_rows": int(len(positions)),
        "broker_order_rows": int(len(orders)),
        "broker_log_rows": int(len(logs)),
        "live_open_order_count": live_open_orders,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase B pre-submit broker-state check.")
    parser.add_argument("--trade-date", required=True, help="Trade date, YYYY-MM-DD.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.trade_date)
    approval = pd.read_csv(paths["approval_csv"], encoding="utf-8-sig")
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    outputs = readonly_summary.get("outputs", {})
    accounts = _read_csv_maybe(outputs.get("accounts"))
    positions = _read_csv_maybe(outputs.get("positions"))
    orders = _read_csv_maybe(outputs.get("orders"))
    logs = _read_csv_maybe(outputs.get("logs"))

    target = approval[approval["approval_status"].astype(str).eq("approved_waiting_precheck")].copy()
    results = pd.DataFrame(
        [
            _build_result_row(row, readonly_summary, accounts, positions, orders, logs)
            for row in target.to_dict(orient="records")
        ]
    )

    approval = approval.copy()
    if "pre_submit_check_reason" not in approval.columns:
        approval["pre_submit_check_reason"] = ""
    if "pre_submit_checked_at" not in approval.columns:
        approval["pre_submit_checked_at"] = ""
    approval["pre_submit_check_reason"] = approval["pre_submit_check_reason"].fillna("").astype(str)
    approval["pre_submit_checked_at"] = approval["pre_submit_checked_at"].fillna("").astype(str)
    approval["pre_submit_check_status"] = approval["pre_submit_check_status"].fillna("").astype(str)

    for row in results.to_dict(orient="records"):
        mask = approval["intent_id"].astype(str).eq(str(row["intent_id"]))
        approval.loc[mask, "pre_submit_check_status"] = row["pre_submit_check_status"]
        approval.loc[mask, "pre_submit_check_reason"] = row["failure_reason"]
        approval.loc[mask, "pre_submit_checked_at"] = row["checked_at"]

    approval.to_csv(paths["approval_csv"], index=False, encoding="utf-8-sig")
    results.to_csv(paths["result_csv"], index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": args.trade_date,
        "checked_intent_count": int(len(results)),
        "passed_count": int(results["can_submit"].sum()) if not results.empty else 0,
        "failed_count": int((results["can_submit"] == 0).sum()) if not results.empty else 0,
        "readonly_probe_status": readonly_summary.get("status", ""),
        "readonly_probe_generated_at": readonly_summary.get("generated_at", ""),
        "outputs": {
            "approval_csv": str(paths["approval_csv"].resolve()),
            "result_csv": str(paths["result_csv"].resolve()),
            "summary_json": str(paths["summary_json"].resolve()),
            "report_md": str(paths["report_md"].resolve()),
        },
        "judgement": {
            "overfit_before": "否。pre-submit check 只做提交前安全校验，不改策略参数。",
            "continue_before": "是。没有这道 fail-closed 闸门，就不该接真实 submit。",
            "overfit_after": "否。校验失败不会反向修改策略信号。",
            "continue_after": "是。若长期稳定通过，再讨论接真实 submit_order。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Stage244 Phase B Pre-submit Broker-state Check",
        "",
        f"- 交易日：`{args.trade_date}`",
        f"- 只读探针状态：`{readonly_summary.get('status', '')}`",
        f"- 只读探针时间：`{readonly_summary.get('generated_at', '')}`",
        "- 目标：在真实提交前，默认 fail-closed 校验 broker/account/order 状态。",
        "",
        "## 检查结果",
        "",
        _to_markdown(
            results,
            [
                "intent_id",
                "pre_submit_check_status",
                "can_submit",
                "failure_reason",
                "broker_account_rows",
                "broker_order_rows",
                "live_open_order_count",
                "checked_at",
            ],
        ),
        "",
        "## 说明",
        "",
        "- 只要 `broker_account_snapshot_missing`、`readonly_probe_not_ready`、`existing_live_open_orders` 任一出现，就不得提交。",
        "- 本阶段仍不触发真实 submit_order()。",
        "",
    ]
    paths["report_md"].write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
