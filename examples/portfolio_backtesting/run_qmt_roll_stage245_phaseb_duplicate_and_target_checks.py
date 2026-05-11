from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage245_phaseb_duplicate_and_target_checks_v1"
APPROVAL_TAG = "stage243_phaseb_approval_v1"
APPROVAL_PREFIX = "qmt_roll_stage243_phaseb_approval"
PRECHECK_TAG = "stage244_phaseb_pre_submit_check_v1"
PRECHECK_PREFIX = "qmt_roll_stage244_phaseb_pre_submit_check"
READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"

ACTIVE_ORDER_STATUSES = {"submitting", "submitted", "nottraded", "parttraded", "partial_filled"}


def _paths(trade_date: str) -> dict[str, Path]:
    date_key = trade_date.replace("-", "")
    return {
        "approval_csv": OUTPUT_DIR / f"{APPROVAL_PREFIX}_ledger_{date_key}_{APPROVAL_TAG}.csv",
        "precheck_csv": OUTPUT_DIR / f"{PRECHECK_PREFIX}_results_{date_key}_{PRECHECK_TAG}.csv",
        "result_csv": OUTPUT_DIR / f"qmt_roll_stage245_phaseb_duplicate_target_results_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"qmt_roll_stage245_phaseb_duplicate_target_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"qmt_roll_stage245_phaseb_duplicate_target_report_{date_key}_{MODEL_TAG}.md",
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


def _normalize_text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _normalize_direction(value: Any) -> str:
    text = _clean_scalar(value).lower()
    mapping = {
        "long": "long",
        "多": "long",
        "direction.long": "long",
        "short": "short",
        "空": "short",
        "direction.short": "short",
    }
    return mapping.get(text, text)


def _normalize_offset(value: Any) -> str:
    text = _clean_scalar(value).lower()
    mapping = {
        "open": "open",
        "开": "open",
        "offset.open": "open",
        "close": "close",
        "平": "close",
        "offset.close": "close",
        "closetoday": "close",
        "closeyesterday": "close",
    }
    return mapping.get(text, text)


def _column(df: pd.DataFrame, *candidates: str) -> pd.Series:
    for name in candidates:
        if name in df.columns:
            return df[name]
    return pd.Series([""] * len(df), index=df.index)


def _duplicate_order_check(current: dict[str, Any], approval: pd.DataFrame, orders: pd.DataFrame) -> tuple[str, str]:
    reasons: list[str] = []
    current_intent = _clean_scalar(current.get("intent_id", ""))
    submit_status = _clean_scalar(current.get("submit_status", ""))
    broker_order_id = _clean_scalar(current.get("broker_order_id", ""))

    if int(approval["intent_id"].astype(str).eq(current_intent).sum()) > 1:
        reasons.append("duplicate_intent_id_in_ledger")

    if broker_order_id:
        reasons.append("intent_already_has_broker_order_id")

    if submit_status not in {"", "not_submitted"}:
        reasons.append(f"intent_submit_status={submit_status}")

    if not orders.empty:
        order_vt_symbol = _normalize_text(_column(orders, "vt_symbol", "symbol"))
        order_direction = _column(orders, "direction").map(_normalize_direction)
        order_offset = _column(orders, "offset").map(_normalize_offset)
        order_status = _normalize_text(_column(orders, "status"))
        same_active = (
            order_vt_symbol.eq(str(current.get("vt_symbol", "")).lower())
            & order_direction.eq(_normalize_direction(current.get("direction", "")))
            & order_offset.eq(_normalize_offset(current.get("offset", "")))
            & order_status.isin(ACTIVE_ORDER_STATUSES)
        )
        if int(same_active.sum()) > 0:
            reasons.append("active_broker_order_same_symbol_direction_offset")

    if reasons:
        return "failed", ";".join(reasons)
    return "passed", ""


def _target_position_check(current: dict[str, Any], positions: pd.DataFrame, orders: pd.DataFrame) -> tuple[str, str]:
    if positions.empty:
        return "not_checked", "position_snapshot_missing"

    vt_symbol = str(current.get("vt_symbol", ""))
    target_direction = _normalize_direction(current.get("direction", ""))
    target_volume = float(pd.to_numeric(current.get("planned_volume"), errors="coerce") or 0.0)

    pos_vt_symbol = _normalize_text(_column(positions, "vt_symbol", "symbol"))
    pos_direction = _column(positions, "direction").map(_normalize_direction)
    pos_volume = pd.to_numeric(_column(positions, "volume", "pos", "position"), errors="coerce").fillna(0.0)
    current_volume = float(pos_volume[pos_vt_symbol.eq(vt_symbol.lower()) & pos_direction.eq(target_direction)].sum())

    pending_same_direction = 0.0
    if not orders.empty:
        order_vt_symbol = _normalize_text(_column(orders, "vt_symbol", "symbol"))
        order_direction = _column(orders, "direction").map(_normalize_direction)
        order_offset = _column(orders, "offset").map(_normalize_offset)
        order_status = _normalize_text(_column(orders, "status"))
        order_volume = pd.to_numeric(_column(orders, "volume", "traded_volume"), errors="coerce").fillna(0.0)
        pending_same_direction = float(
            order_volume[
                order_vt_symbol.eq(vt_symbol.lower())
                & order_direction.eq(target_direction)
                & order_offset.eq("open")
                & order_status.isin(ACTIVE_ORDER_STATUSES)
            ].sum()
        )

    effective_volume = current_volume + pending_same_direction
    if target_volume > 0 and effective_volume >= target_volume:
        return "failed", f"target_position_already_reached:{effective_volume:.4f}>={target_volume:.4f}"
    return "passed", ""


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase B duplicate-order and target-position checks.")
    parser.add_argument("--trade-date", required=True, help="Trade date, YYYY-MM-DD.")
    args = parser.parse_args()

    paths = _paths(args.trade_date)
    approval = pd.read_csv(paths["approval_csv"], encoding="utf-8-sig")
    precheck = pd.read_csv(paths["precheck_csv"], encoding="utf-8-sig")
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    outputs = readonly_summary.get("outputs", {})
    positions = _read_csv_maybe(outputs.get("positions"))
    orders = _read_csv_maybe(outputs.get("orders"))

    merged = approval.merge(
        precheck[["intent_id", "can_submit", "failure_reason", "pre_submit_check_status"]],
        on="intent_id",
        how="left",
        suffixes=("", "_stage244"),
    )

    rows: list[dict[str, Any]] = []
    approval = approval.copy()
    for extra_col in [
        "duplicate_check_status",
        "duplicate_check_reason",
        "target_position_check_status",
        "target_position_check_reason",
        "final_failure_reason",
        "final_checked_at",
    ]:
        if extra_col not in approval.columns:
            approval[extra_col] = ""
        approval[extra_col] = approval[extra_col].fillna("").astype(str)
    if "final_can_submit" not in approval.columns:
        approval["final_can_submit"] = 0
    approval["final_can_submit"] = pd.to_numeric(approval["final_can_submit"], errors="coerce").fillna(0).astype(int)

    for record in merged.to_dict(orient="records"):
        duplicate_status, duplicate_reason = _duplicate_order_check(record, approval, orders)
        target_status, target_reason = _target_position_check(record, positions, orders)
        base_can_submit = int(pd.to_numeric(record.get("can_submit"), errors="coerce") or 0)
        reasons = [str(record.get("failure_reason", "")).strip(), duplicate_reason.strip()]
        if target_status == "failed":
            reasons.append(target_reason.strip())
        final_reasons = ";".join([reason for reason in reasons if reason])
        final_can_submit = 1 if (base_can_submit == 1 and duplicate_status == "passed" and target_status == "passed") else 0
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows.append(
            {
                "trade_date": record.get("trade_date", ""),
                "intent_id": record.get("intent_id", ""),
                "base_can_submit": base_can_submit,
                "duplicate_check_status": duplicate_status,
                "duplicate_check_reason": duplicate_reason,
                "target_position_check_status": target_status,
                "target_position_check_reason": target_reason,
                "final_can_submit": final_can_submit,
                "final_failure_reason": final_reasons,
                "checked_at": checked_at,
            }
        )

        mask = approval["intent_id"].astype(str).eq(str(record.get("intent_id", "")))
        approval.loc[mask, "duplicate_check_status"] = duplicate_status
        approval.loc[mask, "duplicate_check_reason"] = duplicate_reason
        approval.loc[mask, "target_position_check_status"] = target_status
        approval.loc[mask, "target_position_check_reason"] = target_reason
        approval.loc[mask, "final_can_submit"] = int(final_can_submit)
        approval.loc[mask, "final_failure_reason"] = final_reasons
        approval.loc[mask, "final_checked_at"] = checked_at

    result_df = pd.DataFrame(rows)
    approval.to_csv(paths["approval_csv"], index=False, encoding="utf-8-sig")
    result_df.to_csv(paths["result_csv"], index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": args.trade_date,
        "checked_intent_count": int(len(result_df)),
        "final_can_submit_count": int(result_df["final_can_submit"].sum()) if not result_df.empty else 0,
        "blocked_count": int((result_df["final_can_submit"] == 0).sum()) if not result_df.empty else 0,
        "outputs": {
            "approval_csv": str(paths["approval_csv"].resolve()),
            "result_csv": str(paths["result_csv"].resolve()),
            "summary_json": str(paths["summary_json"].resolve()),
            "report_md": str(paths["report_md"].resolve()),
        },
        "judgement": {
            "overfit_before": "否。重复委托和目标持仓校验是执行安全边界，不改策略参数。",
            "continue_before": "是。没有这两道校验，真实执行很容易出现重单和重复开仓事故。",
            "overfit_after": "否。校验只决定能否提交，不会反向修改信号。",
            "continue_after": "是。接下来应继续打通账户快照，而不是急着接真实 submit。",
        },
    }
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    report_lines = [
        "# Stage245 Phase B Duplicate And Target Position Checks",
        "",
        f"- 交易日：`{args.trade_date}`",
        "- 目标：补齐重复委托与目标持仓已达成校验，避免重复送单和重复开仓。",
        "",
        "## 检查结果",
        "",
        _to_markdown(
            result_df,
            [
                "intent_id",
                "base_can_submit",
                "duplicate_check_status",
                "duplicate_check_reason",
                "target_position_check_status",
                "target_position_check_reason",
                "final_can_submit",
                "final_failure_reason",
            ],
        ),
        "",
        "## 说明",
        "",
        "- `duplicate_check_status=failed` 表示本地账本或真实委托快照已显示可能重复提交。",
        "- `target_position_check_status=failed` 表示真实持仓加未完成开仓量已经达到目标，不得再次开仓。",
        "- `target_position_check_status=not_checked` 表示当前缺少真实持仓快照，仍不能放行提交。",
        "",
    ]
    paths["report_md"].write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
