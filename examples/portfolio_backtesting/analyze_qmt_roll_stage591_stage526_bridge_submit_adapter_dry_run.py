from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


MODEL_TAG = "stage591_stage526_bridge_submit_adapter_dry_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run"
LINE_ID = "futures_trend_drawdown30_preserve_return"
ORDER_REFERENCE_PREFIX = "Stage526TCA"

STAGE589_TAG = "stage589_stage526_pre_submit_bridge_mapping_audit_v1"
STAGE589_PREFIX = "qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit"
STAGE589_MAPPING = OUTPUT_DIR / f"{STAGE589_PREFIX}_pre_submit_mapping_ledger_{STAGE589_TAG}.csv"

PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_submit_plan_{MODEL_TAG}.csv"
CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_context_requirements_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_LIVE_CONTEXT_FIELDS = [
    "fresh_contract_snapshot",
    "fresh_account_snapshot",
    "fresh_position_snapshot",
    "live_limit_price",
    "account_equity_before",
    "broker_margin_before",
    "price_band_checked",
    "margin_available_checked",
    "operator_confirmed",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    symbol, exchange = vt_symbol.rsplit(".", 1)
    return symbol, exchange


def _direction(value: Any) -> Direction | None:
    text = _clean(value).upper()
    if text in {"LONG", "BUY", "DIRECTION.LONG", "多"}:
        return Direction.LONG
    if text in {"SHORT", "SELL", "DIRECTION.SHORT", "空"}:
        return Direction.SHORT
    return None


def _offset(value: Any) -> Offset | None:
    text = _clean(value).upper()
    mapping = {
        "OPEN": Offset.OPEN,
        "CLOSE": Offset.CLOSE,
        "CLOSETODAY": Offset.CLOSETODAY,
        "CLOSEYESTERDAY": Offset.CLOSEYESTERDAY,
        "开": Offset.OPEN,
        "平": Offset.CLOSE,
        "平今": Offset.CLOSETODAY,
        "平昨": Offset.CLOSEYESTERDAY,
    }
    return mapping.get(text)


def _exchange(value: str) -> Exchange | None:
    try:
        return Exchange(value)
    except Exception:
        return None


def _make_order_request(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    vt_symbol = _clean(row.get("vt_symbol"))
    symbol, exchange_value = _split_vt_symbol(vt_symbol)
    exchange = _exchange(exchange_value)
    direction = _direction(row.get("direction"))
    offset = _offset(row.get("offset"))
    volume = _to_float(row.get("planned_volume"), 0.0)
    live_limit_price = _to_float(row.get("limit_price"), 0.0)
    reference_price = _to_float(row.get("reference_price"), 0.0)
    bridge_signal_id = _clean(row.get("bridge_signal_id"))
    order_reference = _clean(row.get("order_reference"))
    expected_reference = f"{ORDER_REFERENCE_PREFIX}:{bridge_signal_id}" if bridge_signal_id else ""

    if not bridge_signal_id:
        reasons.append("missing_bridge_signal_id")
    if not order_reference:
        reasons.append("missing_order_reference")
    if expected_reference and order_reference != expected_reference:
        reasons.append("order_reference_not_matching_bridge_signal_id")
    if not symbol or not exchange_value:
        reasons.append("invalid_vt_symbol")
    if exchange is None:
        reasons.append("unsupported_exchange")
    if direction is None:
        reasons.append("invalid_direction")
    if offset is None:
        reasons.append("invalid_offset")
    if volume <= 0:
        reasons.append("invalid_volume")
    if not float(volume).is_integer():
        reasons.append("volume_not_integer_lots")

    # Historical Stage589 rows intentionally do not carry live limit prices.
    # The request draft keeps reference_price for audit only; real submit must
    # replace it with a live checked limit_price from a fresh snapshot.
    price_for_draft = live_limit_price if live_limit_price > 0 else reference_price
    if price_for_draft <= 0:
        reasons.append("missing_reference_or_limit_price")

    payload: dict[str, Any] = {}
    if exchange is not None and direction is not None and offset is not None and price_for_draft > 0 and volume > 0:
        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price_for_draft,
            offset=offset,
            reference=order_reference,
        )
        payload = {
            "symbol": req.symbol,
            "exchange": req.exchange.value,
            "direction": req.direction.value,
            "type": req.type.value,
            "volume": req.volume,
            "price": req.price,
            "offset": req.offset.value,
            "reference": req.reference,
            "vt_symbol": req.vt_symbol,
            "gateway_name": "CTP",
            "price_source": "live_limit_price" if live_limit_price > 0 else "historical_reference_price_for_dry_run_only",
        }
    return payload, reasons


def _build_submit_plan(mapping: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in mapping.to_dict(orient="records"):
        payload, reasons = _make_order_request(row)
        live_context_missing = [field for field in REQUIRED_LIVE_CONTEXT_FIELDS]
        status = "dry_run_order_request_payload_ready" if payload and not reasons else "blocked_contract_invalid"
        vt_orderid = _clean(row.get("vt_orderid"))
        synthetic_vt_orderid = 0
        if vt_orderid:
            status = "blocked_existing_vt_orderid_not_expected_in_dry_run"
            reasons.append("dry_run_input_should_not_already_have_vt_orderid")

        rows.append(
            {
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "checked_at": checked_at,
                "event_id": row.get("event_id"),
                "date": row.get("date"),
                "watch_priority": row.get("watch_priority"),
                "is_stage526_p0": int(_to_float(row.get("is_stage526_p0"), 0.0)),
                "bridge_signal_id": row.get("bridge_signal_id"),
                "order_reference": row.get("order_reference"),
                "reference_carries_bridge_id": int(str(row.get("order_reference", "")).startswith(f"{ORDER_REFERENCE_PREFIX}:")),
                "vt_orderid": vt_orderid,
                "vt_orderid_write_policy": "persist_exact_return_value_from_main_engine_send_order_only",
                "synthetic_vt_orderid_generated": synthetic_vt_orderid,
                "submit_mode": "dry_run",
                "submit_status": status,
                "submit_blockers": ";".join(reasons),
                "real_submit_allowed": 0,
                "send_order_api_called": 0,
                "ctp_connection_attempted": 0,
                "live_context_missing": ";".join(live_context_missing),
                "vt_symbol": row.get("vt_symbol"),
                "direction": row.get("direction"),
                "offset": row.get("offset"),
                "order_type": row.get("order_type"),
                "planned_volume": row.get("planned_volume"),
                "reference_price": row.get("reference_price"),
                "limit_price": row.get("limit_price"),
                "order_request_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        )
    return pd.DataFrame(rows)


def _build_live_context(plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in plan.iterrows():
        for field in REQUIRED_LIVE_CONTEXT_FIELDS:
            rows.append(
                {
                    "bridge_signal_id": row["bridge_signal_id"],
                    "vt_symbol": row["vt_symbol"],
                    "watch_priority": row["watch_priority"],
                    "required_field": field,
                    "present_in_dry_run": 0,
                    "required_before_real_submit": 1,
                    "source": {
                        "fresh_contract_snapshot": "vn.py contract query immediately before submit",
                        "fresh_account_snapshot": "CTP/vn.py account snapshot within 300 seconds",
                        "fresh_position_snapshot": "CTP/vn.py position snapshot within 300 seconds",
                        "live_limit_price": "operator-approved current quote/limit policy",
                        "account_equity_before": "fresh account snapshot",
                        "broker_margin_before": "fresh account/position margin snapshot",
                        "price_band_checked": "exchange/broker order safety check",
                        "margin_available_checked": "pre-submit account risk check",
                        "operator_confirmed": "explicit dry-run-to-real confirmation",
                    }[field],
                }
            )
    return pd.DataFrame(rows)


def _gate(name: str, passed: bool, actual: str, threshold: str, severity: str, judgement: str) -> dict[str, Any]:
    return {
        "gate": name,
        "passed": int(passed),
        "actual": actual,
        "threshold": threshold,
        "severity": severity,
        "judgement": judgement,
    }


def _build_gates(plan: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    row_count = int(len(plan))
    payload_count = int(plan["order_request_json"].astype(str).str.len().gt(2).sum()) if not plan.empty else 0
    p0_count = int(plan["is_stage526_p0"].sum()) if not plan.empty else 0
    ref_count = int(plan["reference_carries_bridge_id"].sum()) if not plan.empty else 0
    vt_count = int(plan["vt_orderid"].astype(str).str.strip().ne("").sum()) if not plan.empty else 0
    synthetic_count = int(plan["synthetic_vt_orderid_generated"].sum()) if not plan.empty else 0
    api_count = int(plan["send_order_api_called"].sum()) if not plan.empty else 0
    ctp_count = int(plan["ctp_connection_attempted"].sum()) if not plan.empty else 0
    context_missing_rows = int((context["present_in_dry_run"].astype(int) == 0).sum()) if not context.empty else 0
    return pd.DataFrame(
        [
            _gate("stage589_mapping_loaded", row_count > 0, str(row_count), ">0", "hard", "Stage589 mapping ledger must be available."),
            _gate("p0_rows_present", p0_count >= 3, str(p0_count), ">=3", "hard", "P0 execution rows must remain visible."),
            _gate("order_reference_carries_bridge_id", ref_count == row_count and row_count > 0, f"{ref_count}/{row_count}", "all rows", "hard", "OrderRequest.reference contract is Stage526TCA:<bridge_signal_id>."),
            _gate("order_request_payload_built", payload_count == row_count and row_count > 0, f"{payload_count}/{row_count}", "all rows", "hard", "Adapter can build auditable OrderRequest payloads."),
            _gate("no_send_order_called", api_count == 0, str(api_count), "0", "hard", "Dry-run must not call main_engine.send_order."),
            _gate("no_ctp_connection_attempted", ctp_count == 0, str(ctp_count), "0", "hard", "Dry-run must not connect CTP."),
            _gate("no_synthetic_vt_orderid", synthetic_count == 0, str(synthetic_count), "0", "hard", "vt_orderid must only come from send_order return."),
            _gate("real_vt_orderid_absent", vt_count == 0, str(vt_count), "0 in dry-run", "hard", "Dry-run correctly remains without live vt_orderid."),
            _gate("live_context_missing_blocks_real_submit", context_missing_rows > 0, str(context_missing_rows), ">0 until real pre-submit", "hard", "Real submit must wait for fresh live context."),
            _gate("zero_bias_claim_allowed", False, "false", "true only after mapped fills", "hard", "No mapped EVENT_ORDER/EVENT_TRADE fills yet."),
        ]
    )


def _decision(plan: pd.DataFrame, gates: pd.DataFrame) -> dict[str, Any]:
    hard = gates[gates["severity"].eq("hard")]
    return {
        "decision": "bridge_submit_adapter_dry_run_ready_live_context_missing",
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "submit_plan_rows": int(len(plan)),
        "p0_rows": int(plan["is_stage526_p0"].sum()) if not plan.empty else 0,
        "order_request_payload_rows": int(plan["order_request_json"].astype(str).str.len().gt(2).sum()) if not plan.empty else 0,
        "real_vt_orderid_mappings": int(plan["vt_orderid"].astype(str).str.strip().ne("").sum()) if not plan.empty else 0,
        "send_order_api_called_count": int(plan["send_order_api_called"].sum()) if not plan.empty else 0,
        "ctp_connection_attempted": bool(int(plan["ctp_connection_attempted"].sum()) if not plan.empty else 0),
        "gates_passed": int(gates["passed"].sum()),
        "gates_total": int(len(gates)),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "overfit_reflection": "No. This is execution plumbing and does not change strategy signals or parameters.",
        "continue_value_reflection": "Yes. It wires Stage526TCA references into a dry-run submit plan while keeping live evidence gates red.",
    }


def _plot(plan: pd.DataFrame, context: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_status, ax_priority, ax_context, ax_gates = axes.flatten()

    status_counts = plan["submit_status"].value_counts().sort_index()
    ax_status.bar(status_counts.index, status_counts.values, color="#0ea5e9")
    ax_status.set_title("Dry-run submit plan status")
    ax_status.tick_params(axis="x", rotation=20)
    ax_status.set_ylabel("rows")

    priority_counts = plan.groupby(["watch_priority", "is_stage526_p0"])["bridge_signal_id"].count().reset_index()
    colors = np.where(priority_counts["is_stage526_p0"].astype(int).eq(1), "#dc2626", "#64748b")
    ax_priority.barh(priority_counts["watch_priority"], priority_counts["bridge_signal_id"], color=colors)
    ax_priority.set_title("P0/P1 rows retained")
    ax_priority.set_xlabel("rows")

    context_counts = context.groupby("required_field")["present_in_dry_run"].sum().reindex(REQUIRED_LIVE_CONTEXT_FIELDS).fillna(0)
    context_colors = np.where(context_counts.gt(0), "#10b981", "#dc2626")
    ax_context.barh(context_counts.index, np.ones(len(context_counts)), color=context_colors)
    ax_context.set_xlim(0, max(1, int(plan.shape[0])))
    ax_context.set_title("Live context present in dry-run")
    ax_context.set_xlabel("red means missing in dry-run")
    for idx, value in enumerate(context_counts):
        ax_context.text(0.5, idx, f"{int(value)} present", va="center", ha="center", color="white", fontsize=8, fontweight="bold")

    gate_colors = np.where(gates["passed"].eq(1), "#10b981", "#dc2626")
    ax_gates.barh(gates["gate"], np.ones(len(gates)), color=gate_colors)
    ax_gates.set_xlim(0, 1)
    ax_gates.set_title("Bridge submit gates")
    ax_gates.tick_params(axis="y", labelsize=8)
    for idx, passed in enumerate(gates["passed"]):
        ax_gates.text(0.5, idx, "PASS" if passed else "FAIL", va="center", ha="center", color="white", fontsize=8, fontweight="bold")

    fig.suptitle("Stage591 Stage526 bridge submit adapter dry-run", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    cols = [col for col in columns if col in df.columns]
    return df.loc[:, cols].head(max_rows).to_markdown(index=False)


def _write_report(plan: pd.DataFrame, context: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage591 Stage526 bridge submit adapter dry-run",
        "",
        f"- decision: `{decision['decision']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`",
        f"- submit_plan_rows: `{decision['submit_plan_rows']}`",
        f"- p0_rows: `{decision['p0_rows']}`",
        f"- order_request_payload_rows: `{decision['order_request_payload_rows']}`",
        f"- real_vt_orderid_mappings: `{decision['real_vt_orderid_mappings']}`",
        f"- send_order_api_called_count: `{decision['send_order_api_called_count']}`",
        f"- ctp_connection_attempted: `{decision['ctp_connection_attempted']}`",
        f"- gates: `{decision['gates_passed']}/{decision['gates_total']}`, hard `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Interpretation",
        "",
        "This run wires Stage589 bridge rows into auditable vn.py OrderRequest payloads with `OrderRequest.reference=Stage526TCA:<bridge_signal_id>`. It remains dry-run only: no CTP connection, no send_order call, and no synthetic vt_orderid. Real submit is still blocked until fresh live contract/account/position snapshots, a live limit price, margin checks, and explicit operator confirmation exist.",
        "",
        "## Submit Plan",
        "",
        _md_table(
            plan,
            [
                "event_id",
                "date",
                "watch_priority",
                "is_stage526_p0",
                "bridge_signal_id",
                "order_reference",
                "submit_status",
                "vt_orderid",
                "send_order_api_called",
                "vt_symbol",
                "direction",
                "offset",
                "planned_volume",
                "reference_price",
            ],
        ),
        "",
        "## Gates",
        "",
        _md_table(gates, ["gate", "passed", "actual", "threshold", "severity", "judgement"], 20),
        "",
        "## Files",
        "",
        f"- submit_plan: `{PLAN_PATH}`",
        f"- live_context_requirements: `{CONTEXT_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- chart: `{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping = _read_csv(STAGE589_MAPPING)
    plan = _build_submit_plan(mapping)
    context = _build_live_context(plan)
    gates = _build_gates(plan, context)
    decision = _decision(plan, gates)

    plan.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")
    context.to_csv(CONTEXT_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(plan, context, gates, decision)
    _write_report(plan, context, gates, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
