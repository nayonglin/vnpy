from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SIGNAL_PLAN_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
    build_official_live_manifest,
    build_official_live_risk_snapshot,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage242_phaseb_order_draft_v1"
OUTPUT_PREFIX = "qmt_roll_stage242_phaseb_order_draft"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _fmt(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.4f}"


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(_fmt)
    return view.to_markdown(index=False)


def _live_deployment_status(live_summary: dict[str, Any]) -> dict[str, Any]:
    variant = live_summary.get("current_variant", {}) or {}
    equity = float(variant.get("end_equity", 0.0) or 0.0)
    return {
        "source": OFFICIAL_LIVE_VERSION,
        "current_total_equity": equity,
        "current_production_equity": equity,
        "current_locked_equity": 0.0,
        "current_expansion_equity": 0.0,
        "gap_to_first_sweep": 0.0,
        "historical_first_sweep_date": "",
    }


def _build_rows(signal_plan: pd.DataFrame, live_summary: dict[str, Any], deployment_status: dict[str, Any]) -> pd.DataFrame:
    trade_date = str(live_summary.get("analysis_end", ""))
    risk = build_official_live_risk_snapshot(live_summary)
    allow_real = int(risk.get("allow_real_new_orders", 0))
    reasons = ",".join(risk.get("reasons", []))

    columns = [
        "trade_date",
        "intent_id",
        "order_group_id",
        "shadow_session_id",
        "strategy_version",
        "strategy_alias",
        "approval_status",
        "approval_required",
        "blocked_reason",
        "risk_level",
        "allow_real_new_orders",
        "deployment_gap_to_first_sweep",
        "current_production_equity",
        "historical_first_sweep_date",
        "vt_symbol",
        "direction",
        "offset",
        "planned_volume",
        "theoretical_price",
        "draft_order_price",
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
    ]
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(signal_plan.to_dict(orient="records"), start=1):
        shadow_session_id = str(row.get("shadow_session_id", ""))
        intent_id = f"PHASEB-{trade_date.replace('-', '')}-{idx:03d}"
        order_group_id = f"{intent_id}-G1"
        theoretical_price = float(pd.to_numeric(row.get("theoretical_price"), errors="coerce") or 0.0)
        proxy_price = float(pd.to_numeric(row.get("real_t1_open_proxy_price"), errors="coerce") or 0.0)
        draft_price = proxy_price if proxy_price > 0 else theoretical_price
        price_source = "real_t1_open_proxy_price" if proxy_price > 0 else "theoretical_price_fallback"
        initial_status = "pending_manual_approval" if allow_real else "blocked_by_gate"
        rows.append(
            {
                "trade_date": trade_date,
                "intent_id": intent_id,
                "order_group_id": order_group_id,
                "shadow_session_id": shadow_session_id,
                "strategy_version": OFFICIAL_LIVE_VERSION,
                "strategy_alias": OFFICIAL_LIVE_ALIAS,
                "approval_status": initial_status,
                "approval_required": 1 if allow_real else 0,
                "blocked_reason": "" if allow_real else reasons,
                "risk_level": risk.get("risk_level", ""),
                "allow_real_new_orders": allow_real,
                "deployment_gap_to_first_sweep": float(deployment_status.get("gap_to_first_sweep", 0.0)),
                "current_production_equity": float(deployment_status.get("current_production_equity", 0.0)),
                "historical_first_sweep_date": str(deployment_status.get("historical_first_sweep_date", "")),
                "vt_symbol": str(row.get("vt_symbol", "")),
                "direction": str(row.get("direction", "")),
                "offset": str(row.get("offset", "")),
                "planned_volume": float(pd.to_numeric(row.get("volume"), errors="coerce") or 0.0),
                "theoretical_price": theoretical_price,
                "draft_order_price": draft_price,
                "draft_price_source": price_source,
                "proxy_quality": str(row.get("proxy_quality", "")),
                "operator_action": "",
                "operator_id": "",
                "operator_note": "",
                "approved_at": "",
                "submit_mode": "phase_b_manual_approve_system_submit",
                "pre_submit_check_status": "not_run",
                "broker_order_id": "",
                "submit_status": "not_submitted",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase B semi-auto order draft for the official live profile.")
    parser.add_argument("--trade-date", default="", help="Expected trade date. Defaults to official live summary analysis_end.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    live_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    deployment_status = _live_deployment_status(live_summary)
    signal_plan = _read_csv_maybe(OFFICIAL_LIVE_SIGNAL_PLAN_PATH)

    target_date = args.trade_date or str(live_summary.get("analysis_end", ""))
    if target_date:
        live_summary["analysis_end"] = target_date

    draft_df = _build_rows(signal_plan, live_summary, deployment_status)
    date_key = target_date.replace("-", "") if target_date else "latest"

    draft_csv = OUTPUT_DIR / f"{OUTPUT_PREFIX}_draft_{date_key}_{MODEL_TAG}.csv"
    summary_json = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json"
    report_md = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md"

    draft_df.to_csv(draft_csv, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "trade_date": target_date,
        "strategy_version": OFFICIAL_LIVE_VERSION,
        "strategy_alias": OFFICIAL_LIVE_ALIAS,
        "signal_count": int(len(signal_plan)),
        "draft_count": int(len(draft_df)),
        "pending_manual_approval_count": int(draft_df["approval_status"].eq("pending_manual_approval").sum()) if not draft_df.empty else 0,
        "blocked_by_gate_count": int(draft_df["approval_status"].eq("blocked_by_gate").sum()) if not draft_df.empty else 0,
        "risk_snapshot": build_official_live_risk_snapshot(live_summary),
        "deployment_status": deployment_status,
        "official_manifest": build_official_live_manifest(),
        "outputs": {
            "draft_csv": str(draft_csv.resolve()),
            "summary_json": str(summary_json.resolve()),
            "report_md": str(report_md.resolve()),
        },
        "judgement": {
            "overfit_before": "否。Phase B draft 只是把既有信号和部署 gate 映射成待审批委托草案，不改策略参数。",
            "continue_before": "是。没有 order draft，就无法形成真正的半自动执行。",
            "overfit_after": "否。没有根据这份草案反向改信号或手数。",
            "continue_after": "是。下一步应接 approve/reject 状态切换，而不是直接接真实 submit。",
        },
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Stage242 Phase B Order Draft",
        "",
        f"- 交易日：`{target_date}`",
        f"- 策略版本：`{OFFICIAL_LIVE_VERSION}`",
        f"- 策略别名：`{OFFICIAL_LIVE_ALIAS}`",
        "- 目标：把当日信号转成 `Phase B` 待审批委托草案，不触发真实下单。",
        "",
        "## 风险与部署状态",
        "",
        f"- 风险级别：`{build_official_live_risk_snapshot(live_summary).get('risk_level', '')}`",
        f"- 是否允许真实新增开仓：`{build_official_live_risk_snapshot(live_summary).get('allow_real_new_orders', '')}`",
        f"- 当前生产权益：`{float(deployment_status.get('current_production_equity', 0.0)):,.0f}`",
        "",
        "## 待审批委托草案",
        "",
        _to_markdown(
            draft_df,
            [
                "intent_id",
                "approval_status",
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "theoretical_price",
                "draft_order_price",
                "draft_price_source",
                "risk_level",
            ],
        ),
        "",
        "## 说明",
        "",
        "- `approval_status=pending_manual_approval` 表示允许进入人工审批。",
        "- `approval_status=blocked_by_gate` 表示部署 gate 未通过，不得进入人工审批。",
        "- 如果 official live `signal_plan` 为空，本阶段会生成空草案并保持 fail-closed，不回落到 Stage78。",
        "- 本阶段不做真实下单，只生成待审批对象。",
        "",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
