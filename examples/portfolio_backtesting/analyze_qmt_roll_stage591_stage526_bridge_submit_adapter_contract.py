from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


MODEL_TAG = "stage591_stage526_bridge_submit_adapter_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage591_stage526_bridge_submit_adapter_contract"
STAGE589_TAG = "stage589_stage526_pre_submit_bridge_mapping_audit_v1"
STAGE589_PREFIX = "qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit"
STAGE589_MAPPING = OUTPUT_DIR / f"{STAGE589_PREFIX}_pre_submit_mapping_ledger_{STAGE589_TAG}.csv"

CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_STAGE526_TEST_ORDERS"
REFERENCE_PREFIX = "Stage526TCA:"

SUBMIT_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_submit_plan_{MODEL_TAG}.csv"
MAPPING_WRITER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mapping_writer_contract_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _direction(value: Any) -> Direction | None:
    text = _clean(value).upper()
    mapping = {
        "LONG": Direction.LONG,
        "多": Direction.LONG,
        "DIRECTION.LONG": Direction.LONG,
        "SHORT": Direction.SHORT,
        "空": Direction.SHORT,
        "DIRECTION.SHORT": Direction.SHORT,
    }
    return mapping.get(text)


def _offset(value: Any) -> Offset | None:
    text = _clean(value).upper()
    mapping = {
        "OPEN": Offset.OPEN,
        "开": Offset.OPEN,
        "OFFSET.OPEN": Offset.OPEN,
        "CLOSE": Offset.CLOSE,
        "平": Offset.CLOSE,
        "OFFSET.CLOSE": Offset.CLOSE,
        "CLOSETODAY": Offset.CLOSETODAY,
        "平今": Offset.CLOSETODAY,
        "OFFSET.CLOSETODAY": Offset.CLOSETODAY,
        "CLOSEYESTERDAY": Offset.CLOSEYESTERDAY,
        "平昨": Offset.CLOSEYESTERDAY,
        "OFFSET.CLOSEYESTERDAY": Offset.CLOSEYESTERDAY,
    }
    return mapping.get(text)


def _order_type(value: Any) -> OrderType | None:
    text = _clean(value).upper()
    mapping = {
        "LIMIT": OrderType.LIMIT,
        "限价": OrderType.LIMIT,
        "ORDERTYPE.LIMIT": OrderType.LIMIT,
        "MARKET": OrderType.MARKET,
        "市价": OrderType.MARKET,
        "ORDERTYPE.MARKET": OrderType.MARKET,
    }
    return mapping.get(text)


def _build_order_request(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    bridge_signal_id = _clean(row.get("bridge_signal_id"))
    reference = _clean(row.get("order_reference"))
    symbol = _clean(row.get("symbol"))
    exchange_text = _clean(row.get("exchange"))
    direction = _direction(row.get("direction"))
    offset = _offset(row.get("offset"))
    order_type = _order_type(row.get("order_type")) or OrderType.LIMIT
    volume = _to_float(row.get("planned_volume"), 0.0)
    price = _to_float(row.get("limit_price"), 0.0) or _to_float(row.get("reference_price"), 0.0)

    if not bridge_signal_id:
        blockers.append("bridge_signal_id_missing")
    if not reference.startswith(REFERENCE_PREFIX):
        blockers.append("reference_missing_stage526tca_prefix")
    if bridge_signal_id and reference != f"{REFERENCE_PREFIX}{bridge_signal_id}":
        blockers.append("reference_not_equal_bridge_signal_id")
    if not symbol:
        blockers.append("symbol_missing")
    if not exchange_text:
        blockers.append("exchange_missing")
    if direction is None:
        blockers.append("direction_invalid")
    if offset is None:
        blockers.append("offset_invalid")
    if volume <= 0:
        blockers.append("volume_invalid")
    if not float(volume).is_integer():
        blockers.append("volume_not_integer_lots")
    if order_type == OrderType.LIMIT and price <= 0:
        blockers.append("limit_price_invalid")

    payload: dict[str, Any] = {}
    if not blockers and direction and offset:
        exchange = Exchange(exchange_text)
        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=order_type,
            volume=volume,
            price=price,
            offset=offset,
            reference=reference,
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
        }
    return payload, blockers


def _load_stage589() -> pd.DataFrame:
    if not STAGE589_MAPPING.exists():
        raise FileNotFoundError(STAGE589_MAPPING)
    return pd.read_csv(STAGE589_MAPPING, encoding="utf-8-sig")


def _submit_rows(mapping: pd.DataFrame, mode: str, confirm_text: str) -> pd.DataFrame:
    real_env_enabled = _env_enabled("STAGE526_REAL_ORDER_ENABLED")
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows: list[dict[str, Any]] = []

    for raw in mapping.to_dict(orient="records"):
        payload, blockers = _build_order_request(raw)
        status = "request_ready_dry_run"
        send_order_api_called = 0
        vt_orderid = ""
        vt_orderid_source = "future_main_engine_send_order_return"
        real_submit_allowed = 0
        main_engine_send_order_invocation = "not_called"

        if blockers:
            status = "blocked"
        if mode == "real":
            if not real_env_enabled:
                blockers.append("stage526_real_order_env_disabled")
            if confirm_text != CONFIRM_TEXT:
                blockers.append("real_submit_confirmation_missing")
            blockers.append("fresh_broker_snapshot_not_attached")
            blockers.append("main_engine_not_injected")
            status = "blocked"
        elif mode == "dry-run":
            blockers.append("dry_run_no_send_order")
        else:
            blockers.append("unsupported_mode")
            status = "blocked"

        if blockers and status != "blocked":
            status = "request_ready_dry_run"

        rows.append(
            {
                "line_id": "futures_trend_drawdown30_preserve_return",
                "model_tag": MODEL_TAG,
                "checked_at": checked_at,
                "mode": mode,
                "event_id": raw.get("event_id", ""),
                "date": raw.get("date", ""),
                "watch_priority": raw.get("watch_priority", ""),
                "is_stage526_p0": _to_int(raw.get("is_stage526_p0"), 0),
                "bridge_signal_id": raw.get("bridge_signal_id", ""),
                "adapter_intent_id": raw.get("adapter_intent_id", ""),
                "order_reference": raw.get("order_reference", ""),
                "request_builder_status": status,
                "request_builder_blockers": ";".join(dict.fromkeys(blockers)),
                "send_order_api_called": send_order_api_called,
                "main_engine_send_order_invocation": main_engine_send_order_invocation,
                "real_submit_allowed": real_submit_allowed,
                "vt_orderid": vt_orderid,
                "vt_orderid_source": vt_orderid_source,
                "mapping_status_after_adapter": "awaiting_live_send_order_return",
                "vt_symbol": raw.get("vt_symbol", ""),
                "symbol": raw.get("symbol", ""),
                "exchange": raw.get("exchange", ""),
                "direction": raw.get("direction", ""),
                "offset": raw.get("offset", ""),
                "order_type": raw.get("order_type", ""),
                "volume": _to_float(raw.get("planned_volume"), 0.0),
                "price": _to_float(raw.get("limit_price"), 0.0) or _to_float(raw.get("reference_price"), 0.0),
                "gateway_name": "CTP",
                "order_request_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                "contract_snapshot_required_before_real_submit": 1,
                "fresh_broker_snapshot_required_before_real_submit": 1,
                "operator_confirmation_required": CONFIRM_TEXT,
            }
        )
    return pd.DataFrame(rows)


def _mapping_writer_contract(submit_plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in submit_plan.to_dict(orient="records"):
        rows.append(
            {
                "bridge_signal_id": row["bridge_signal_id"],
                "order_reference": row["order_reference"],
                "expected_submit_call": "vt_orderid = main_engine.send_order(req, gateway_name)",
                "write_timing": "immediately_after_send_order_returns_before_waiting_for_events",
                "vt_orderid_write_policy": "write_actual_return_only_never_synthetic",
                "mapping_ledger_key": "bridge_signal_id",
                "event_join_key": "vt_orderid",
                "event_sources_after_submit": "EVENT_ORDER,EVENT_TRADE,EVENT_TICK",
                "required_next_metrics": "filled_volume,unfilled_volume,cancelled_volume,avg_fill_price,VWAP,implementation_shortfall,participation",
                "dry_run_value": "",
                "dry_run_status": "slot_created_no_real_value",
            }
        )
    return pd.DataFrame(rows)


def _gates(submit_plan: pd.DataFrame, mapping_writer: pd.DataFrame, mode: str) -> pd.DataFrame:
    p0 = submit_plan[submit_plan["is_stage526_p0"].eq(1)]
    order_json_ready = int(submit_plan["order_request_json"].astype(str).str.len().gt(2).sum())
    reference_ok = int(submit_plan["order_reference"].astype(str).str.startswith(REFERENCE_PREFIX).all())
    bridge_unique = int(submit_plan["bridge_signal_id"].astype(str).is_unique)
    send_order_count = int(pd.to_numeric(submit_plan["send_order_api_called"], errors="coerce").fillna(0).sum())
    real_vt_orderids = int(submit_plan["vt_orderid"].astype(str).str.len().gt(0).sum())

    return pd.DataFrame(
        [
            {
                "gate": "stage589_mapping_loaded",
                "actual": f"{len(submit_plan)} rows",
                "threshold": ">=5",
                "passed": int(len(submit_plan) >= 5),
                "hard_gate": 1,
                "judgement": "Stage589 mapping rows are available.",
            },
            {
                "gate": "order_request_payload_ready",
                "actual": f"{order_json_ready}/{len(submit_plan)}",
                "threshold": "all rows",
                "passed": int(order_json_ready == len(submit_plan) and len(submit_plan) > 0),
                "hard_gate": 1,
                "judgement": "Bridge-aware OrderRequest payload can be built from mapping ledger.",
            },
            {
                "gate": "stage526_reference_prefix",
                "actual": str(bool(reference_ok)),
                "threshold": "all references start Stage526TCA:",
                "passed": reference_ok,
                "hard_gate": 1,
                "judgement": "OrderRequest.reference carries bridge id.",
            },
            {
                "gate": "bridge_signal_id_unique",
                "actual": str(bool(bridge_unique)),
                "threshold": "unique",
                "passed": bridge_unique,
                "hard_gate": 1,
                "judgement": "Mapping ledger can be keyed by bridge_signal_id.",
            },
            {
                "gate": "p0_payload_slots_ready",
                "actual": f"{len(p0)} P0 rows",
                "threshold": ">=3",
                "passed": int(len(p0) >= 3 and p0["order_request_json"].astype(str).str.len().gt(2).all()),
                "hard_gate": 1,
                "judgement": "P0 rows have payload slots.",
            },
            {
                "gate": "dry_run_send_order_zero",
                "actual": str(send_order_count),
                "threshold": "0",
                "passed": int(send_order_count == 0),
                "hard_gate": 1,
                "judgement": "This audit does not call CTP or send_order.",
            },
            {
                "gate": "mapping_writer_contract_ready",
                "actual": f"{len(mapping_writer)} writer rows",
                "threshold": "same as submit rows",
                "passed": int(len(mapping_writer) == len(submit_plan) and len(mapping_writer) > 0),
                "hard_gate": 1,
                "judgement": "Future submit adapter has a precise vt_orderid write contract.",
            },
            {
                "gate": "real_vt_orderid_present",
                "actual": str(real_vt_orderids),
                "threshold": ">=9 P0 samples eventually",
                "passed": int(real_vt_orderids > 0),
                "hard_gate": 1,
                "judgement": "Still absent by design in dry-run.",
            },
            {
                "gate": "real_submit_allowed",
                "actual": str(bool(pd.to_numeric(submit_plan["real_submit_allowed"], errors="coerce").fillna(0).sum())),
                "threshold": "false for this audit",
                "passed": int(pd.to_numeric(submit_plan["real_submit_allowed"], errors="coerce").fillna(0).sum() == 0),
                "hard_gate": 1,
                "judgement": "Real submit remains blocked until fresh broker snapshot and main_engine are attached.",
            },
            {
                "gate": "zero_execution_bias_claim_allowed",
                "actual": "false",
                "threshold": "requires live mapped fills",
                "passed": 0,
                "hard_gate": 1,
                "judgement": "No real fills, no execution-bias close.",
            },
        ]
    )


def _decision(submit_plan: pd.DataFrame, gates: pd.DataFrame, mode: str) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    return {
        "decision": "bridge_submit_adapter_contract_ready_real_submit_blocked",
        "mode": mode,
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "submit_rows": int(len(submit_plan)),
        "p0_submit_rows": int(submit_plan["is_stage526_p0"].eq(1).sum()),
        "order_request_payload_ready": int(submit_plan["order_request_json"].astype(str).str.len().gt(2).sum()),
        "send_order_api_called_count": int(pd.to_numeric(submit_plan["send_order_api_called"], errors="coerce").fillna(0).sum()),
        "real_vt_orderid_mappings": int(submit_plan["vt_orderid"].astype(str).str.len().gt(0).sum()),
        "real_submit_allowed_count": int(pd.to_numeric(submit_plan["real_submit_allowed"], errors="coerce").fillna(0).sum()),
        "gates_passed": int(gates["passed"].sum()),
        "gates_total": int(len(gates)),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "overfit_reflection": "No. This is execution plumbing and field-contract validation, not strategy or return tuning.",
        "continue_value_reflection": "Yes. It turns Stage589's contract into an adapter-facing payload and write policy, while keeping real submit blocked.",
    }


def _plot(submit_plan: pd.DataFrame, mapping_writer: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_status, ax_fields, ax_p0, ax_gates = axes.flatten()

    status_counts = submit_plan["request_builder_status"].value_counts()
    ax_status.bar(status_counts.index, status_counts.values, color="#0ea5e9")
    ax_status.set_title("Submit adapter status")
    ax_status.set_ylabel("rows")
    ax_status.tick_params(axis="x", rotation=15)

    field_matrix = pd.DataFrame(
        np.column_stack(
            [
                submit_plan["bridge_signal_id"].astype(str).str.len().gt(0).astype(int).to_numpy(),
                submit_plan["order_reference"].astype(str).str.startswith(REFERENCE_PREFIX).astype(int).to_numpy(),
                submit_plan["order_request_json"].astype(str).str.len().gt(2).astype(int).to_numpy(),
                submit_plan["vt_orderid"].astype(str).str.len().gt(0).astype(int).to_numpy(),
                pd.to_numeric(submit_plan["real_submit_allowed"], errors="coerce").fillna(0).astype(int).to_numpy(),
            ]
        ),
        columns=["bridge_id", "reference", "payload", "vt_orderid", "real_allowed"],
        index=submit_plan["vt_symbol"].astype(str).to_list(),
    )
    ax_fields.grid(False)
    im = ax_fields.imshow(field_matrix.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax_fields.set_title("Field readiness")
    ax_fields.set_xticks(range(len(field_matrix.columns)))
    ax_fields.set_xticklabels(field_matrix.columns, rotation=30, ha="right")
    ax_fields.set_yticks(range(len(field_matrix.index)))
    ax_fields.set_yticklabels(field_matrix.index)
    for row_idx in range(field_matrix.shape[0]):
        for col_idx in range(field_matrix.shape[1]):
            value = int(field_matrix.iloc[row_idx, col_idx])
            ax_fields.text(
                col_idx,
                row_idx,
                str(value),
                ha="center",
                va="center",
                color="white" if value == 0 else "#064e3b",
                fontweight="bold",
                fontsize=8,
            )
    fig.colorbar(im, ax=ax_fields, fraction=0.046, pad=0.04)

    p0 = submit_plan[submit_plan["is_stage526_p0"].eq(1)].copy()
    ax_p0.barh(p0["vt_symbol"], p0["volume"], color="#f97316")
    ax_p0.set_title("P0 planned volume slots")
    ax_p0.set_xlabel("lots")

    gate_colors = np.where(gates["passed"].eq(1), "#10b981", "#dc2626")
    ax_gates.barh(gates["gate"], np.ones(len(gates)), color=gate_colors)
    ax_gates.set_xlim(0, 1)
    ax_gates.set_title("Contract gates")
    ax_gates.tick_params(axis="y", labelsize=8)
    for idx, passed in enumerate(gates["passed"]):
        ax_gates.text(0.5, idx, "PASS" if passed else "FAIL", va="center", ha="center", color="white", fontweight="bold", fontsize=8)

    fig.suptitle("Stage591 Stage526 bridge submit adapter contract", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    return df.head(max_rows).to_markdown(index=False)


def _write_report(submit_plan: pd.DataFrame, mapping_writer: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage591 Stage526 bridge submit adapter contract",
        "",
        f"- decision: `{decision['decision']}`",
        f"- mode: `{decision['mode']}`",
        f"- submit_rows: `{decision['submit_rows']}`",
        f"- p0_submit_rows: `{decision['p0_submit_rows']}`",
        f"- order_request_payload_ready: `{decision['order_request_payload_ready']}`",
        f"- send_order_api_called_count: `{decision['send_order_api_called_count']}`",
        f"- real_vt_orderid_mappings: `{decision['real_vt_orderid_mappings']}`",
        f"- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`",
        f"- gates: `{decision['gates_passed']}/{decision['gates_total']}`, hard `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Interpretation",
        "",
        "Stage589's mapping contract is now represented as adapter-facing OrderRequest payloads and an explicit vt_orderid write policy. This is still dry-run only: it does not connect CTP, does not inject MainEngine, does not call send_order, and does not create synthetic vt_orderid values.",
        "",
        "## Submit Plan",
        "",
        _md_table(
            submit_plan[
                [
                    "event_id",
                    "vt_symbol",
                    "watch_priority",
                    "bridge_signal_id",
                    "order_reference",
                    "request_builder_status",
                    "request_builder_blockers",
                    "send_order_api_called",
                    "vt_orderid",
                    "volume",
                    "price",
                ]
            ],
            20,
        ),
        "",
        "## Mapping Writer Contract",
        "",
        _md_table(mapping_writer, 20),
        "",
        "## Gates",
        "",
        _md_table(gates, 20),
        "",
        "## Outputs",
        "",
        f"- submit_plan: `{SUBMIT_PLAN_PATH}`",
        f"- mapping_writer_contract: `{MAPPING_WRITER_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- chart: `{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Stage526 bridge-aware submit adapter contract without calling send_order.")
    parser.add_argument("--mode", choices=["dry-run", "real"], default="dry-run")
    parser.add_argument("--confirm-real-submit", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping = _load_stage589()
    submit_plan = _submit_rows(mapping, args.mode, args.confirm_real_submit)
    mapping_writer = _mapping_writer_contract(submit_plan)
    gates = _gates(submit_plan, mapping_writer, args.mode)
    decision = _decision(submit_plan, gates, args.mode)

    submit_plan.to_csv(SUBMIT_PLAN_PATH, index=False, encoding="utf-8-sig")
    mapping_writer.to_csv(MAPPING_WRITER_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(submit_plan, mapping_writer, gates, decision)
    _write_report(submit_plan, mapping_writer, gates, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
