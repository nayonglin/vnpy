from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage589_stage526_pre_submit_bridge_mapping_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit"

STAGE587_TAG = "stage587_stage526_live_tca_bridge_dry_run_v1"
STAGE587_PREFIX = "qmt_roll_stage587_stage526_live_tca_bridge_dry_run"
STAGE587_INTENT = OUTPUT_DIR / f"{STAGE587_PREFIX}_intent_ledger_{STAGE587_TAG}.csv"
STAGE587_GATES = OUTPUT_DIR / f"{STAGE587_PREFIX}_gates_{STAGE587_TAG}.csv"

STAGE249_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage249_phaseb_submit_adapter.py"
STAGE250_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage250_phaseb_vnpy_order_request_builder.py"
STAGE587_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage587_stage526_live_tca_bridge_dry_run.py"

MAPPING_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pre_submit_mapping_ledger_{MODEL_TAG}.csv"
ADAPTER_CAPABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_adapter_capability_matrix_{MODEL_TAG}.csv"
FIELD_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_contract_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_SYMBOLS = {"fu2509.SHFE", "lc2505.GFEX", "AP505.CZCE"}
CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_REAL_ORDERS"
ORDER_REFERENCE_PREFIX = "Stage526TCA"

STAGE526_REFERENCE = {
    "ending_equity": 23_369_505,
    "total_return_pct": 3699.9195,
    "max_drawdown_pct": -36.2670,
    "sharpe": 1.6385,
    "ulcer": 14.4691,
    "total_slippage": 1_342_190,
    "trade_count": 905,
    "win_rate_pct": 53.6330,
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _num(value: Any, default: float = 0.0) -> float:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed) or math.isinf(float(parsed)):
        return default
    return float(parsed)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return str(value).strip() != ""


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    return tuple(vt_symbol.rsplit(".", 1))  # type: ignore[return-value]


def _normalize_direction(side: str) -> str:
    text = str(side).strip().lower()
    if text in {"buy", "long", "多"}:
        return "LONG"
    if text in {"sell", "short", "空"}:
        return "SHORT"
    return ""


def _normalize_offset(offset: str) -> str:
    text = str(offset).strip().lower()
    if text == "open":
        return "OPEN"
    if text == "close":
        return "CLOSE"
    return text.upper()


def build_mapping_ledger(intent: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in intent.iterrows():
        vt_symbol = str(row.get("vt_symbol", ""))
        symbol, exchange = _split_vt_symbol(vt_symbol)
        bridge_signal_id = str(row.get("bridge_signal_id", "")).strip()
        event_id = str(row.get("event_id", "")).strip()
        order_ref = f"{ORDER_REFERENCE_PREFIX}:{bridge_signal_id}" if bridge_signal_id else ""
        order_volume = _num(row.get("order_volume"), 0.0)
        order_price = _num(row.get("backtest_fill_price"), 0.0)
        direction = _normalize_direction(str(row.get("execution_side", "")))
        offset = _normalize_offset(str(row.get("offset_type", "")))
        watch_priority = str(row.get("watch_priority", ""))
        is_p0 = int(watch_priority.startswith("P0") or vt_symbol in P0_SYMBOLS)
        row_status = "awaiting_live_send_order_return"
        blockers = []
        if not bridge_signal_id:
            blockers.append("missing_bridge_signal_id")
            row_status = "contract_blocked"
        if not vt_symbol or not symbol or not exchange:
            blockers.append("invalid_vt_symbol")
            row_status = "contract_blocked"
        if not direction:
            blockers.append("invalid_direction")
            row_status = "contract_blocked"
        if not offset:
            blockers.append("invalid_offset")
            row_status = "contract_blocked"
        if order_volume <= 0:
            blockers.append("invalid_order_volume")
            row_status = "contract_blocked"
        if order_price <= 0:
            blockers.append("missing_or_nonpositive_reference_price")
        rows.append(
            {
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "mapping_created_at": now_text,
                "mapping_mode": "dry_run_contract_only",
                "event_id": event_id,
                "date": row.get("date", ""),
                "watch_priority": watch_priority,
                "is_stage526_p0": is_p0,
                "bridge_signal_id": bridge_signal_id,
                "adapter_intent_id": bridge_signal_id,
                "vt_orderid": "",
                "vt_orderid_source": "future_main_engine_send_order_return",
                "mapping_status": row_status,
                "mapping_blockers": ";".join(blockers),
                "order_reference": order_ref,
                "reference_contract": f"OrderRequest.reference must include {ORDER_REFERENCE_PREFIX}:<bridge_signal_id>",
                "vt_symbol": vt_symbol,
                "symbol": symbol,
                "exchange": exchange,
                "direction": direction,
                "offset": offset,
                "order_type": "LIMIT",
                "planned_volume": order_volume,
                "reference_price": order_price,
                "limit_price": "",
                "order_submit_at": "",
                "order_submit_price": "",
                "account_equity_before": "",
                "broker_margin_before": "",
                "send_order_api_called": 0,
                "ctp_connection_attempted": 0,
                "real_submit_allowed": 0,
                "confirm_text_required": CONFIRM_TEXT,
                "audit_note": "No vt_orderid is generated in dry-run. Future submit adapter must persist the actual send_order return value here.",
            }
        )
    return pd.DataFrame(rows)


def build_field_contract() -> pd.DataFrame:
    rows = [
        ("bridge_signal_id", "string", "yes", "Stage526/Stage575 stable intent id; joins signal intent to future order id."),
        ("adapter_intent_id", "string", "yes", "Use bridge_signal_id as the adapter intent id to prevent PhaseB intent mismatch."),
        ("order_reference", "string", "yes", "OrderRequest.reference must contain Stage526TCA:<bridge_signal_id>."),
        ("vt_orderid", "string", "real-submit only", "Must be copied from main_engine.send_order(req, gateway_name) return value."),
        ("vt_orderid_source", "string", "yes", "Must state future_main_engine_send_order_return or explicit test fixture source."),
        ("order_submit_at", "datetime", "real-submit only", "Submit timestamp before broker call or immediately after return."),
        ("order_submit_price", "float", "real-submit only", "Actual limit/market price used by broker adapter."),
        ("order_type", "string", "yes", "LIMIT/MARKET/other explicit order type."),
        ("limit_price", "float", "real-submit if LIMIT", "Actual limit price."),
        ("account_equity_before", "float", "real-submit only", "Fresh broker account equity before submit."),
        ("broker_margin_before", "float", "real-submit only", "Fresh broker margin before submit."),
        ("send_order_api_called", "int", "yes", "Must remain 0 in dry-run; real-submit must count exact calls."),
        ("ctp_connection_attempted", "int", "yes", "Must remain 0 in this audit."),
        ("real_submit_allowed", "int", "yes", "Must remain 0 unless explicit environment and confirmation gates pass."),
    ]
    return pd.DataFrame(rows, columns=["field", "type", "required_when", "description"])


def build_adapter_capability(mapping: pd.DataFrame) -> pd.DataFrame:
    stage249 = _read_text(STAGE249_SCRIPT)
    stage250 = _read_text(STAGE250_SCRIPT)
    stage587 = _read_text(STAGE587_SCRIPT)
    stage589_ready = {
        "script": "analyze_qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit.py",
        "role": "new_pre_submit_bridge_mapping_contract",
        "has_bridge_signal_id": 1,
        "has_vt_orderid_slot": 1,
        "reference_carries_bridge_id": 1,
        "send_order_called": 0,
        "real_submit_blocked": 1,
        "notes": "Creates dry-run mapping rows; future submit adapter must fill vt_orderid from send_order return.",
    }
    rows = [
        {
            "script": _relative(STAGE249_SCRIPT),
            "role": "legacy_phaseb_submit_adapter_dry_run",
            "has_bridge_signal_id": int("bridge_signal_id" in stage249),
            "has_vt_orderid_slot": int("vt_orderid" in stage249),
            "reference_carries_bridge_id": int(ORDER_REFERENCE_PREFIX in stage249),
            "send_order_called": int("send_order(" in stage249),
            "real_submit_blocked": int("real_submit_adapter_not_implemented" in stage249),
            "notes": "Has broker_order_id placeholder, but no Stage526 bridge_signal_id/vt_orderid mapping.",
        },
        {
            "script": _relative(STAGE250_SCRIPT),
            "role": "legacy_phaseb_order_request_builder",
            "has_bridge_signal_id": int("bridge_signal_id" in stage250),
            "has_vt_orderid_slot": int("vt_orderid" in stage250),
            "reference_carries_bridge_id": int(ORDER_REFERENCE_PREFIX in stage250),
            "send_order_called": int("send_order(" in stage250),
            "real_submit_blocked": int("stage250_never_calls_send_order" in stage250),
            "notes": "Builds OrderRequest.reference with Stage250PhaseB intent_id, not Stage526TCA bridge id.",
        },
        {
            "script": _relative(STAGE587_SCRIPT),
            "role": "live_tca_reducer_contract",
            "has_bridge_signal_id": int("bridge_signal_id" in stage587),
            "has_vt_orderid_slot": int("bridge_vt_orderid" in stage587),
            "reference_carries_bridge_id": int(ORDER_REFERENCE_PREFIX in stage587),
            "send_order_called": int("send_order(" in stage587),
            "real_submit_blocked": 1,
            "notes": "Reducer requires explicit vt_orderid; no submit mapping writer.",
        },
        stage589_ready,
    ]
    capability = pd.DataFrame(rows)
    capability["contract_ready"] = (
        capability["has_bridge_signal_id"].astype(int)
        & capability["has_vt_orderid_slot"].astype(int)
        & capability["real_submit_blocked"].astype(int)
    )
    capability["mapping_rows_available"] = len(mapping)
    return capability


def _gate(gate: str, passed: bool, actual: str, required: str, severity: str, judgement: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": int(bool(passed)),
        "actual": actual,
        "required": required,
        "severity": severity,
        "judgement": judgement,
    }


def build_gates(mapping: pd.DataFrame, capability: pd.DataFrame, stage587_gates: pd.DataFrame) -> pd.DataFrame:
    p0_mapping = int(pd.to_numeric(mapping["is_stage526_p0"], errors="coerce").fillna(0).sum())
    vt_orderid_count = int(mapping["vt_orderid"].apply(_present).sum())
    unique_bridge = int(mapping["bridge_signal_id"].nunique())
    row_count = int(len(mapping))
    stage249_contract = capability[capability["role"].eq("legacy_phaseb_submit_adapter_dry_run")]
    stage250_contract = capability[capability["role"].eq("legacy_phaseb_order_request_builder")]
    stage589_contract = capability[capability["role"].eq("new_pre_submit_bridge_mapping_contract")]
    old_adapter_has_mapping = bool(
        not stage249_contract.empty
        and int(stage249_contract.iloc[0]["has_bridge_signal_id"]) == 1
        and int(stage249_contract.iloc[0]["has_vt_orderid_slot"]) == 1
    )
    old_builder_carries_bridge_ref = bool(
        not stage250_contract.empty
        and int(stage250_contract.iloc[0]["reference_carries_bridge_id"]) == 1
    )
    new_contract_ready = bool(not stage589_contract.empty and int(stage589_contract.iloc[0]["contract_ready"]) == 1)
    stage587_missing_map = stage587_gates[
        stage587_gates["gate"].astype(str).eq("explicit_stage526_vt_orderid_mapping_present")
    ]
    stage587_map_gate_still_fail = bool(not stage587_missing_map.empty and int(stage587_missing_map.iloc[0].get("passed", 0)) == 0)
    return pd.DataFrame(
        [
            _gate("dry_run_no_ctp_connection", True, "0", "0", "hard", "script only creates contract rows"),
            _gate("send_order_api_called_count_zero", True, "0", "0", "hard", "no broker send_order call in this audit"),
            _gate("stage587_intent_loaded", row_count > 0, str(row_count), ">0", "hard", "Stage587 intent ledger loaded"),
            _gate("bridge_signal_id_unique", unique_bridge == row_count, f"{unique_bridge}/{row_count}", "all rows unique", "hard", "stable join id has no duplicates"),
            _gate("p0_mapping_slots_created", p0_mapping >= len(P0_SYMBOLS), str(p0_mapping), f">={len(P0_SYMBOLS)}", "hard", "P0 rows have mapping slots"),
            _gate("new_pre_submit_contract_ready", new_contract_ready, str(int(new_contract_ready)), "1", "hard", "Stage589 contract creates bridge/vt_orderid slots"),
            _gate("legacy_stage249_has_mapping_writer", old_adapter_has_mapping, str(int(old_adapter_has_mapping)), "1", "medium", "legacy submit adapter still lacks bridge mapping writer"),
            _gate("legacy_stage250_reference_carries_bridge_id", old_builder_carries_bridge_ref, str(int(old_builder_carries_bridge_ref)), "1", "medium", "legacy OrderRequest reference does not carry Stage526TCA bridge id"),
            _gate("real_vt_orderid_mapping_present", vt_orderid_count > 0, str(vt_orderid_count), ">0", "hard", "still requires future send_order return values"),
            _gate("stage587_p0_mapping_gap_remains", stage587_map_gate_still_fail, "true", "true until live submit", "hard", "Stage587 correctly remains red before real vt_orderid"),
            _gate("zero_execution_bias_claim_allowed", False, "not allowed", "allowed only after mapped P0 live fills", "hard", "contract row is not live TCA evidence"),
        ]
    )


def write_chart(mapping: pd.DataFrame, capability: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    ax = axes[0, 0]
    status_counts = mapping["mapping_status"].value_counts().sort_index()
    ax.bar(status_counts.index.astype(str), status_counts.values, color="#4e79a7")
    ax.set_title("Pre-submit mapping status")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=20)
    for idx, value in enumerate(status_counts.values):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom", fontsize=9)

    ax = axes[0, 1]
    cap_cols = ["has_bridge_signal_id", "has_vt_orderid_slot", "reference_carries_bridge_id", "real_submit_blocked"]
    heat = capability[cap_cols].astype(int).to_numpy()
    ax.imshow(heat, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(capability)))
    ax.set_yticklabels(capability["role"].astype(str).tolist(), fontsize=8)
    ax.set_xticks(range(len(cap_cols)))
    ax.set_xticklabels(cap_cols, rotation=30, ha="right", fontsize=8)
    ax.set_title("Adapter capability matrix")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, str(int(heat[i, j])), ha="center", va="center", fontsize=8)

    ax = axes[1, 0]
    priority = mapping.groupby("watch_priority")["bridge_signal_id"].count().sort_values(ascending=False)
    ax.bar(priority.index.astype(str), priority.values, color="#59a14f")
    ax.set_title("Mapping slots by watch priority")
    ax.set_ylabel("rows")
    ax.tick_params(axis="x", rotation=20)
    for idx, value in enumerate(priority.values):
        ax.text(idx, value, str(int(value)), ha="center", va="bottom", fontsize=9)

    ax = axes[1, 1]
    gate_plot = gates.copy()
    gate_plot["plot_value"] = np.where(gate_plot["passed"].astype(int).eq(1), 1, -1)
    colors = np.where(gate_plot["passed"].astype(int).eq(1), "#2e7d32", "#c62828")
    ypos = np.arange(len(gate_plot))
    ax.barh(ypos, gate_plot["plot_value"], color=colors)
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_yticks(ypos)
    ax.set_yticklabels(gate_plot["gate"], fontsize=8)
    ax.set_xlim(-1.05, 1.05)
    ax.set_title("Bridge mapping gates")
    ax.set_xlabel("fail=-1, pass=1")
    ax.invert_yaxis()

    fig.suptitle("Stage589 Stage526 pre-submit bridge mapping audit", fontsize=15)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def write_report(
    mapping: pd.DataFrame,
    capability: pd.DataFrame,
    field_contract: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    text = f"""# Stage589 Stage526 Pre-submit Bridge Mapping Audit

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- created_at: `{decision['created_at']}`
- decision: `{decision['decision']}`
- promotion_allowed: `{decision['promotion_allowed']}`
- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`

## Scope

This stage creates a dry-run/pre-submit mapping contract for Stage526 TCA. It does not connect to CTP, does not call `send_order`, does not modify strategy alpha, and does not run a return backtest.

## External Research Judgment

The official vn.py gateway contract requires `send_order(req)` to return `vt_orderid`, while order and trade lifecycles are published through `EVENT_ORDER` and `EVENT_TRADE`. Therefore the correct bridge is:

`bridge_signal_id -> OrderRequest.reference -> send_order returned vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK -> TCA`.

No live `vt_orderid` is generated in this dry-run audit.

## Stage526 Reference

| metric | value |
| --- | ---: |
| ending_equity | {STAGE526_REFERENCE['ending_equity']} |
| total_return_pct | {STAGE526_REFERENCE['total_return_pct']:.4f} |
| max_drawdown_pct | {STAGE526_REFERENCE['max_drawdown_pct']:.4f} |
| sharpe | {STAGE526_REFERENCE['sharpe']:.4f} |
| ulcer | {STAGE526_REFERENCE['ulcer']:.4f} |
| total_slippage | {STAGE526_REFERENCE['total_slippage']} |
| trade_count | {STAGE526_REFERENCE['trade_count']} |
| win_rate_pct | {STAGE526_REFERENCE['win_rate_pct']:.4f} |

## Key Results

- mapping rows: `{decision['mapping_rows']}`
- P0 mapping slots: `{decision['p0_mapping_slots']}`
- real vt_orderid mappings: `{decision['real_vt_orderid_mappings']}`
- gates: `{decision['gates_passed']}/{decision['gates_total']}`
- send_order_api_called_count: `0`
- ctp_connection_attempted: `0`

## Mapping Ledger

{_md_table(mapping, columns=['event_id', 'date', 'watch_priority', 'bridge_signal_id', 'vt_orderid', 'mapping_status', 'order_reference', 'vt_symbol', 'direction', 'offset', 'planned_volume', 'reference_price'], max_rows=20)}

## Adapter Capability Matrix

{_md_table(capability, max_rows=20)}

## Field Contract

{_md_table(field_contract, max_rows=30)}

## Gates

{_md_table(gates, max_rows=20)}

## Visual Read

- Top-left shows every row is still `awaiting_live_send_order_return`; this is expected for a dry-run contract.
- Top-right shows the new Stage589 contract has bridge id and vt_orderid slots, while legacy Stage249/250 do not yet carry Stage526TCA mapping end to end.
- Bottom-left confirms all P0/P1 intent rows have mapping slots.
- Bottom-right remains red on real vt_orderid and zero-bias claim; the contract does not count as live TCA evidence.

## Next Step

Wire this contract into the future submit-capable adapter:

1. Build `OrderRequest.reference = Stage526TCA:<bridge_signal_id>`.
2. Immediately after `main_engine.send_order(req, gateway_name)`, persist the returned `vt_orderid`.
3. Capture `EVENT_ORDER`, `EVENT_TRADE`, and benchmark ticks/minutes.
4. Re-run Stage587 reducer; only real mapped P0 fills can close execution-bias gates.

## Overfitting Reflection

- Before run: no. This is execution evidence plumbing, not signal tuning.
- After run: no. The output keeps live evidence gates red and refuses synthetic `vt_orderid`.

## Continued Value Reflection

- Before run: yes. Stage526 cannot prove zero execution bias without a signal-to-order mapping.
- After run: yes. The mapping slot now exists as a contract; the remaining blocker is real submit-return `vt_orderid` and mapped P0 fills.

## Output Files

- mapping ledger: `{MAPPING_LEDGER_PATH}`
- adapter capability: `{ADAPTER_CAPABILITY_PATH}`
- field contract: `{FIELD_CONTRACT_PATH}`
- gates: `{GATES_PATH}`
- decision: `{DECISION_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    intent = _read_csv(STAGE587_INTENT)
    stage587_gates = _read_csv(STAGE587_GATES)
    mapping = build_mapping_ledger(intent)
    field_contract = build_field_contract()
    capability = build_adapter_capability(mapping)
    gates = build_gates(mapping, capability, stage587_gates)

    mapping.to_csv(MAPPING_LEDGER_PATH, index=False, encoding="utf-8-sig")
    capability.to_csv(ADAPTER_CAPABILITY_PATH, index=False, encoding="utf-8-sig")
    field_contract.to_csv(FIELD_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "decision": "pre_submit_bridge_mapping_contract_ready_real_vt_orderid_absent",
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "mapping_rows": int(len(mapping)),
        "p0_mapping_slots": int(pd.to_numeric(mapping["is_stage526_p0"], errors="coerce").fillna(0).sum()),
        "real_vt_orderid_mappings": int(mapping["vt_orderid"].apply(_present).sum()),
        "send_order_api_called_count": 0,
        "ctp_connection_attempted": False,
        "gates_passed": int(gates["passed"].sum()),
        "gates_total": int(len(gates)),
        "hard_gates_passed": int(gates[gates["severity"].eq("hard")]["passed"].sum()),
        "hard_gates_total": int((gates["severity"] == "hard").sum()),
        "next_actions": [
            "Modify the future submit-capable adapter to write OrderRequest.reference=Stage526TCA:<bridge_signal_id>.",
            "Persist vt_orderid immediately from main_engine.send_order(req, gateway_name) return value.",
            "Feed mapped EVENT_ORDER/EVENT_TRADE/EVENT_TICK rows back into Stage587 reducer.",
            "Do not claim zero execution bias until P0 live TCA samples are mapped and valid.",
        ],
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(mapping, capability, gates)
    write_report(mapping, capability, field_contract, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
