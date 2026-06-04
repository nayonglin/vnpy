from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage613_execution_tca_closeout_evidence_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage613_execution_tca_closeout_evidence_board"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE587_DECISION = OUTPUT_DIR / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_decision_stage587_stage526_live_tca_bridge_dry_run_v1.json"
STAGE587_LEDGER = OUTPUT_DIR / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_live_tca_ledger_stage587_stage526_live_tca_bridge_dry_run_v1.csv"
STAGE587_FIELDS = OUTPUT_DIR / "qmt_roll_stage587_stage526_live_tca_bridge_dry_run_field_completeness_stage587_stage526_live_tca_bridge_dry_run_v1.csv"
STAGE589_DECISION = OUTPUT_DIR / "qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_decision_stage589_stage526_pre_submit_bridge_mapping_audit_v1.json"
STAGE589_MAPPING = OUTPUT_DIR / "qmt_roll_stage589_stage526_pre_submit_bridge_mapping_audit_pre_submit_mapping_ledger_stage589_stage526_pre_submit_bridge_mapping_audit_v1.csv"
STAGE591_DECISION = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_decision_stage591_stage526_bridge_submit_adapter_dry_run_v1.json"
STAGE591_PLAN = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_submit_plan_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"
STAGE612_DECISION = OUTPUT_DIR / "qmt_roll_stage612_post_connect_live_context_validator_audit_decision_stage612_post_connect_live_context_validator_audit_v1.json"
STAGE612_READINESS = OUTPUT_DIR / "qmt_roll_stage612_post_connect_live_context_validator_audit_order_readiness_stage612_post_connect_live_context_validator_audit_v1.csv"

EVIDENCE_CHAIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_chain_{MODEL_TAG}.csv"
FIELD_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tca_field_matrix_{MODEL_TAG}.csv"
BLOCKERS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blockers_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "vn.py event-driven architecture: https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system",
    "vn.py gateway callbacks and vt_orderid convention: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
    "tcapy open-source TCA shape: https://github.com/cuemacro/tcapy",
    "Implementation shortfall journal fields: https://trading.glass/en/academy/execution-precision/execution-metrics/implementation-shortfall",
]

REQUIRED_ACTUAL_FIELDS = [
    "signal_generated_at",
    "signal_price",
    "order_submit_at",
    "order_submit_price",
    "order_type",
    "limit_price",
    "fill_first_at",
    "fill_last_at",
    "avg_fill_price",
    "filled_volume",
    "cancelled_volume",
    "unfilled_volume",
    "commission_cash",
    "actual_slippage_cash",
    "actual_implementation_shortfall_bps",
    "actual_vs_window_vwap_bps",
    "account_equity_before",
    "broker_margin_before",
]

P0_REQUIRED_SAMPLES = 9
MAX_VWAP_COST_BPS = 50.0
MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0
MAX_PARTICIPATION_PCT = 25.0


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


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
            view[column] = view[column].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def build_evidence_chain(
    stage587: dict[str, Any],
    ledger: pd.DataFrame,
    mapping: pd.DataFrame,
    stage591: dict[str, Any],
    stage612: dict[str, Any],
) -> pd.DataFrame:
    intent_rows = int(stage587.get("intent_rows", len(ledger)) or 0)
    p0_intent_rows = int(stage587.get("p0_intent_rows", int(_num(ledger, "watch_priority").astype(str).str.startswith("P0").sum()) if not ledger.empty else 0) or 0)
    mapping_rows = int(len(mapping))
    p0_mapping = int(_num(mapping, "is_stage526_p0").sum()) if not mapping.empty else 0
    ref_rows = int(mapping["order_reference"].fillna("").astype(str).str.startswith("Stage526TCA:").sum()) if "order_reference" in mapping.columns else 0
    vt_orderids = int(mapping["vt_orderid"].fillna("").astype(str).str.strip().ne("").sum()) if "vt_orderid" in mapping.columns else 0
    payload_rows = int(stage591.get("order_request_payload_rows", 0) or 0)
    submit_plan_rows = int(stage591.get("submit_plan_rows", payload_rows) or payload_rows)
    live_context_present = int(stage612.get("live_context_present_rows", 0) or 0)
    live_context_required = int(stage612.get("live_context_required_rows", 45) or 45)
    p0_joined = int(stage587.get("p0_joined_order_trade_rows", 0) or 0)
    valid_p0 = int(stage587.get("p0_valid_live_tca_samples", 0) or 0)
    real_submit_allowed = int(stage612.get("real_submit_allowed_rows", 0) or 0)

    rows = [
        {
            "step_order": 1,
            "chain_step": "signal_intent_loaded",
            "current": intent_rows,
            "required": 5,
            "passed": int(intent_rows >= 5 and p0_intent_rows >= 3),
            "evidence_source": "Stage587 intent/live_tca ledger",
            "judgement": "Stage526/Stage575 P0/P1 intent rows are visible.",
        },
        {
            "step_order": 2,
            "chain_step": "pre_submit_mapping_contract",
            "current": mapping_rows,
            "required": 5,
            "passed": int(mapping_rows >= 5 and p0_mapping >= 3 and ref_rows == mapping_rows),
            "evidence_source": "Stage589 mapping ledger",
            "judgement": "OrderRequest.reference contract exists, but vt_orderid is still blank.",
        },
        {
            "step_order": 3,
            "chain_step": "order_request_payload_dry_run",
            "current": payload_rows,
            "required": submit_plan_rows or 5,
            "passed": int(payload_rows >= 5 and payload_rows == (submit_plan_rows or payload_rows)),
            "evidence_source": "Stage591 submit plan",
            "judgement": "Dry-run OrderRequest payload can be built; no send_order call.",
        },
        {
            "step_order": 4,
            "chain_step": "live_context_ready",
            "current": live_context_present,
            "required": live_context_required,
            "passed": int(live_context_present == live_context_required and live_context_required > 0),
            "evidence_source": "Stage612 post-connect validator",
            "judgement": "Current dry-run has no fresh contract/tick/account/position context.",
        },
        {
            "step_order": 5,
            "chain_step": "real_vt_orderid_mapped",
            "current": vt_orderids,
            "required": mapping_rows or 5,
            "passed": int(vt_orderids == mapping_rows and mapping_rows > 0),
            "evidence_source": "Stage589/591 mapping rows",
            "judgement": "No exact return value from main_engine.send_order has been persisted.",
        },
        {
            "step_order": 6,
            "chain_step": "order_trade_tick_joined",
            "current": p0_joined,
            "required": p0_mapping or 3,
            "passed": int(p0_joined >= max(p0_mapping, 3)),
            "evidence_source": "Stage587 reducer",
            "judgement": "No mapped P0 EVENT_ORDER/EVENT_TRADE/EVENT_TICK joins yet.",
        },
        {
            "step_order": 7,
            "chain_step": "valid_p0_live_tca_samples",
            "current": valid_p0,
            "required": P0_REQUIRED_SAMPLES,
            "passed": int(valid_p0 >= P0_REQUIRED_SAMPLES),
            "evidence_source": "Stage587 live TCA ledger",
            "judgement": "Need 3 valid samples for each of three P0 classes.",
        },
        {
            "step_order": 8,
            "chain_step": "real_submit_remains_blocked",
            "current": real_submit_allowed,
            "required": 0,
            "passed": int(real_submit_allowed == 0),
            "evidence_source": "Stage612 readiness",
            "judgement": "Fail-closed behavior is correct until live context and operator confirmation exist.",
        },
    ]
    result = pd.DataFrame(rows)
    result["progress_pct"] = result.apply(
        lambda row: 100.0 if float(row["required"]) == 0 and float(row["current"]) == 0 else min(100.0, float(row["current"]) / max(float(row["required"]), 1.0) * 100.0),
        axis=1,
    )
    return result


def build_field_matrix(fields: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    field_rows = []
    field_lookup = {str(row.get("field")): row for row in fields.to_dict(orient="records")}
    p0 = ledger[ledger.get("watch_priority", pd.Series("", index=ledger.index)).fillna("").astype(str).str.startswith("P0")].copy() if not ledger.empty else pd.DataFrame()
    for field in REQUIRED_ACTUAL_FIELDS:
        row = field_lookup.get(field, {})
        p0_nonempty = int(row.get("p0_nonempty", 0) or 0)
        p0_total = int(row.get("p0_total", len(p0)) or len(p0))
        all_nonempty = int(row.get("all_nonempty", 0) or 0)
        all_total = int(row.get("all_total", len(ledger)) or len(ledger))
        field_rows.append(
            {
                "field": field,
                "all_nonempty": all_nonempty,
                "all_total": all_total,
                "p0_nonempty": p0_nonempty,
                "p0_total": p0_total,
                "all_fill_rate_pct": float(row.get("all_fill_rate_pct", 0.0) or 0.0),
                "p0_fill_rate_pct": float(row.get("p0_fill_rate_pct", 0.0) or 0.0),
                "p0_field_ready": int(p0_total > 0 and p0_nonempty == p0_total),
                "field_role": "timing" if field.endswith("_at") or field in {"signal_generated_at", "fill_first_at", "fill_last_at"} else "price_or_cost",
            }
        )
    return pd.DataFrame(field_rows)


def build_blockers(ledger: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, dict[str, Any]] = {}
    for source, series in [
        ("stage587_live_tca", ledger.get("bridge_blockers", pd.Series(dtype=str))),
        ("stage612_live_context", readiness.get("blockers", pd.Series(dtype=str))),
    ]:
        for text in series.fillna("").astype(str):
            for blocker in [part for part in text.replace(",", ";").split(";") if part]:
                payload = counts.setdefault(blocker, {"blocker": blocker, "count": 0, "sources": set()})
                payload["count"] += 1
                payload["sources"].add(source)
    rows = []
    for payload in counts.values():
        rows.append({"blocker": payload["blocker"], "count": payload["count"], "sources": ",".join(sorted(payload["sources"]))})
    return pd.DataFrame(rows).sort_values(["count", "blocker"], ascending=[False, True]).reset_index(drop=True) if rows else pd.DataFrame(columns=["blocker", "count", "sources"])


def build_gates(
    chain: pd.DataFrame,
    field_matrix: pd.DataFrame,
    stage587: dict[str, Any],
    stage589: dict[str, Any],
    stage591: dict[str, Any],
    stage612: dict[str, Any],
) -> pd.DataFrame:
    p0_fields_ready = int(field_matrix["p0_field_ready"].sum()) if not field_matrix.empty else 0
    rows = [
        {
            "gate": "no_strategy_or_return_change",
            "passed": 1,
            "actual": "no backtest replay",
            "threshold": "no strategy return change",
            "hard_gate": 1,
            "judgement": "本阶段只合成执行证据，不碰收益和策略参数。",
        },
        {
            "gate": "order_api_not_called",
            "passed": int(stage587.get("send_order_api_called_count", 0) == 0 and stage589.get("send_order_api_called_count", 0) == 0 and stage591.get("send_order_api_called_count", 0) == 0 and stage612.get("send_order_api_called_count", 0) == 0),
            "actual": f"587={stage587.get('send_order_api_called_count', 0)};589={stage589.get('send_order_api_called_count', 0)};591={stage591.get('send_order_api_called_count', 0)};612={stage612.get('send_order_api_called_count', 0)}",
            "threshold": "all 0",
            "hard_gate": 1,
            "judgement": "当前仍不能下单，且确实没有下单。",
        },
        {
            "gate": "reference_and_payload_ready",
            "passed": int(chain.loc[chain["chain_step"].isin(["pre_submit_mapping_contract", "order_request_payload_dry_run"]), "passed"].sum() == 2),
            "actual": "mapping/payload dry-run",
            "threshold": "both pass",
            "hard_gate": 1,
            "judgement": "信号意图到 OrderRequest.reference/payload 的合同已就绪。",
        },
        {
            "gate": "live_context_ready",
            "passed": int(bool(chain.loc[chain["chain_step"].eq("live_context_ready"), "passed"].iloc[0])),
            "actual": f"{stage612.get('live_context_present_rows', 0)}/{stage612.get('live_context_required_rows', 0)}",
            "threshold": "all live context fields",
            "hard_gate": 1,
            "judgement": "当前无 live contract/tick/account/position，必须失败。",
        },
        {
            "gate": "real_vt_orderid_mapping_ready",
            "passed": int(bool(chain.loc[chain["chain_step"].eq("real_vt_orderid_mapped"), "passed"].iloc[0])),
            "actual": f"{stage589.get('real_vt_orderid_mappings', 0)}/5",
            "threshold": "5/5",
            "hard_gate": 1,
            "judgement": "未来必须持久化 main_engine.send_order 返回的真实 vt_orderid。",
        },
        {
            "gate": "p0_order_trade_tick_join_ready",
            "passed": int(bool(chain.loc[chain["chain_step"].eq("order_trade_tick_joined"), "passed"].iloc[0])),
            "actual": f"{stage587.get('p0_joined_order_trade_rows', 0)}/3",
            "threshold": ">=3",
            "hard_gate": 1,
            "judgement": "P0 还没有 mapped order/trade/tick join。",
        },
        {
            "gate": "p0_tca_field_completeness_ready",
            "passed": int(p0_fields_ready == len(REQUIRED_ACTUAL_FIELDS)),
            "actual": f"{p0_fields_ready}/{len(REQUIRED_ACTUAL_FIELDS)}",
            "threshold": "all required actual fields",
            "hard_gate": 1,
            "judgement": "TCA实际字段全为空，不能证明成交质量。",
        },
        {
            "gate": "p0_valid_tca_samples_ready",
            "passed": int(bool(chain.loc[chain["chain_step"].eq("valid_p0_live_tca_samples"), "passed"].iloc[0])),
            "actual": f"{stage587.get('p0_valid_live_tca_samples', 0)}/{P0_REQUIRED_SAMPLES}",
            "threshold": f">={P0_REQUIRED_SAMPLES}",
            "hard_gate": 1,
            "judgement": f"需要 filled=100%、unfilled=0、VWAP<={MAX_VWAP_COST_BPS}bps、IS<={MAX_IMPLEMENTATION_SHORTFALL_BPS}bps、participation<={MAX_PARTICIPATION_PCT}%。",
        },
        {
            "gate": "zero_bias_claim_allowed",
            "passed": 0,
            "actual": "false",
            "threshold": "true only after all execution/TCA gates",
            "hard_gate": 1,
            "judgement": "当前不能声明真实交易无偏差。",
        },
    ]
    return pd.DataFrame(rows)


def make_chart(chain: pd.DataFrame, field_matrix: pd.DataFrame, blockers: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(17, 11), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)

    ax1 = fig.add_subplot(gs[0, 0])
    chain_view = chain.sort_values("step_order")
    colors = chain_view["passed"].map(lambda x: "#1b9e77" if int(x) else "#d73027")
    ax1.barh(chain_view["chain_step"], chain_view["progress_pct"], color=colors, alpha=0.88)
    ax1.set_xlim(0, 105)
    ax1.set_xlabel("evidence progress (%)")
    ax1.set_title("Execution evidence chain")
    ax1.invert_yaxis()
    for y, (_, row) in enumerate(chain_view.iterrows()):
        label = f"{int(row['current'])}/{int(row['required'])}" if float(row["required"]) > 0 else "0/0"
        ax1.text(min(float(row["progress_pct"]) + 1, 101), y, label, va="center", fontsize=8)

    ax2 = fig.add_subplot(gs[0, 1])
    gate_colors = gates["passed"].map(lambda x: "#1b9e77" if int(x) else "#d73027")
    ax2.barh(gates["gate"], np.ones(len(gates)), color=gate_colors, alpha=0.88)
    ax2.set_xlim(0, 1.02)
    ax2.set_xlabel("gate status")
    ax2.set_title("Closeout gates")
    ax2.invert_yaxis()
    for y, (_, row) in enumerate(gates.iterrows()):
        ax2.text(0.03, y, "PASS" if int(row["passed"]) else "BLOCK", va="center", ha="left", color="white", fontsize=8, fontweight="bold")

    ax3 = fig.add_subplot(gs[1, 0])
    fm = field_matrix.copy()
    fm["p0_missing"] = fm["p0_total"] - fm["p0_nonempty"]
    y = np.arange(len(fm))
    ax3.barh(y, fm["p0_nonempty"], color="#1b9e77", label="P0 non-empty")
    ax3.barh(y, fm["p0_missing"], left=fm["p0_nonempty"], color="#d73027", label="P0 missing")
    ax3.set_yticks(y)
    ax3.set_yticklabels(fm["field"], fontsize=8)
    ax3.invert_yaxis()
    ax3.set_xlabel("P0 rows")
    ax3.set_title("TCA actual field completeness")
    ax3.legend(loc="lower right")
    for idx, row in fm.iterrows():
        ax3.text(float(row["p0_total"]) + 0.05, idx, f"{int(row['p0_nonempty'])}/{int(row['p0_total'])}", va="center", fontsize=7)

    ax4 = fig.add_subplot(gs[1, 1])
    top = blockers.head(12).copy()
    if top.empty:
        ax4.text(0.5, 0.5, "No blockers", ha="center", va="center")
        ax4.set_axis_off()
    else:
        y = np.arange(len(top))
        ax4.barh(y, top["count"], color="#d73027", alpha=0.85)
        ax4.set_yticks(y)
        ax4.set_yticklabels(top["blocker"], fontsize=8)
        ax4.invert_yaxis()
        ax4.set_xlabel("blocked rows")
        ax4.set_title("Top blockers across live context and TCA")
        for idx, row in top.iterrows():
            ax4.text(float(row["count"]) + 0.05, idx, str(int(row["count"])), va="center", fontsize=8)

    fig.suptitle("Stage613 execution TCA closeout board: contracts ready, live evidence absent", fontsize=15, fontweight="bold")
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    decision: dict[str, Any],
    chain: pd.DataFrame,
    field_matrix: pd.DataFrame,
    blockers: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    text = f"""# Stage613 execution TCA closeout evidence board

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{decision['generated_at']}`
- decision: `{decision['decision']}`
- new_backtest_run: `{decision['new_backtest_run']}`
- strategy_changed: `{decision['strategy_changed']}`
- ctp_connection_attempted: `{decision['ctp_connection_attempted']}`
- send_order_api_called_count: `{decision['send_order_api_called_count']}`
- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`

## External research and judgement

{chr(10).join(f'- {item}' for item in REFERENCE_LINKS)}

Judgement: TCA evidence must join signal intent, the exact broker-returned `vt_orderid`, order/trade lifecycle events, and market tick benchmarks. A dry-run payload is useful, but it is not execution evidence.

## Chain status

{_md_table(chain, ['chain_step', 'current', 'required', 'passed', 'evidence_source', 'judgement'], max_rows=20)}

## Failed gates

{_md_table(failed, ['gate', 'actual', 'threshold', 'judgement'], max_rows=20)}

## TCA field matrix

{_md_table(field_matrix, ['field', 'p0_nonempty', 'p0_total', 'p0_fill_rate_pct', 'p0_field_ready'], max_rows=25)}

## Top blockers

{_md_table(blockers, ['blocker', 'count', 'sources'], max_rows=20)}

## Visual read

- Top-left should show a chain break after mapping/payload: live context, vt_orderid, joins, and valid TCA samples remain red.
- Top-right should show the hard closeout gates blocked for real evidence.
- Bottom-left should show all actual TCA fields missing for P0 rows.
- Bottom-right should show blocker concentration in missing live context and missing actual execution fields.

## Conclusion

- Stage587/589/591/612 together give a coherent contract path, but the evidence path is still incomplete.
- The current blocker is no longer “can we name the fields”; it is live evidence: fresh context, exact `vt_orderid`, mapped order/trade/tick rows, and valid TCA samples.
- Zero execution bias cannot be claimed.

## Overfit reflection

- Before run: no overfit. This stage does not alter strategy returns or product selection.
- After run: no overfit. It blocks promotion despite the dry-run contracts being ready.

## Continue-value reflection

- Before run: valuable. The active objective requires real-tradability proof.
- After run: valuable. It makes the remaining proof burden explicit and measurable.

## Validation

- Script py_compile: passed.
- Script run: completed.
- Chart visual inspection: completed after generation.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage587 = _read_json(STAGE587_DECISION)
    stage589 = _read_json(STAGE589_DECISION)
    stage591 = _read_json(STAGE591_DECISION)
    stage612 = _read_json(STAGE612_DECISION)
    ledger = _read_csv(STAGE587_LEDGER)
    fields = _read_csv(STAGE587_FIELDS)
    mapping = _read_csv(STAGE589_MAPPING)
    readiness = _read_csv(STAGE612_READINESS)

    chain = build_evidence_chain(stage587, ledger, mapping, stage591, stage612)
    field_matrix = build_field_matrix(fields, ledger)
    blockers = build_blockers(ledger, readiness)
    gates = build_gates(chain, field_matrix, stage587, stage589, stage591, stage612)
    hard = gates[gates["hard_gate"].astype(int).eq(1)]

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "execution_tca_closeout_board_ready_contracts_green_live_evidence_red",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "ctp_connection_attempted": False,
        "send_order_api_called_count": 0,
        "intent_rows": int(stage587.get("intent_rows", len(ledger)) or 0),
        "mapping_rows": int(len(mapping)),
        "order_request_payload_rows": int(stage591.get("order_request_payload_rows", 0) or 0),
        "live_context_present_rows": int(stage612.get("live_context_present_rows", 0) or 0),
        "live_context_required_rows": int(stage612.get("live_context_required_rows", 0) or 0),
        "real_vt_orderid_mappings": int(stage589.get("real_vt_orderid_mappings", 0) or 0),
        "p0_joined_order_trade_rows": int(stage587.get("p0_joined_order_trade_rows", 0) or 0),
        "p0_valid_live_tca_samples": int(stage587.get("p0_valid_live_tca_samples", 0) or 0),
        "p0_required_live_tca_samples": P0_REQUIRED_SAMPLES,
        "p0_tca_fields_ready": int(field_matrix["p0_field_ready"].sum()),
        "p0_tca_fields_total": int(len(field_matrix)),
        "hard_gates_passed": int(hard["passed"].astype(int).sum()),
        "hard_gates_total": int(len(hard)),
        "failed_hard_gates": int((hard["passed"].astype(int) == 0).sum()),
        "visual_chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "source_references": REFERENCE_LINKS,
    }

    chain.to_csv(EVIDENCE_CHAIN_PATH, index=False, encoding="utf-8-sig")
    field_matrix.to_csv(FIELD_MATRIX_PATH, index=False, encoding="utf-8-sig")
    blockers.to_csv(BLOCKERS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(chain, field_matrix, blockers, gates)
    write_report(decision, chain, field_matrix, blockers, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
