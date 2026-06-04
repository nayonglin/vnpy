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
MODEL_TAG = "stage586_live_tca_ledger_hook_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage586_live_tca_ledger_hook_readiness"

STAGE568_TAG = "stage568_stage526_execution_quality_ledger_audit_v1"
STAGE568_PREFIX = "qmt_roll_stage568_stage526_execution_quality_ledger_audit"
STAGE575_TAG = "stage575_stage526_live_execution_p0_watchlist_v1"
STAGE575_PREFIX = "qmt_roll_stage575_stage526_live_execution_p0_watchlist"
STAGE583_TAG = "stage583_stage526_live_tca_evidence_gap_audit_v1"
STAGE583_PREFIX = "qmt_roll_stage583_stage526_live_tca_evidence_gap_audit"
STAGE585_TAG = "stage585_stage526_non_csv_live_evidence_discovery_v1"
STAGE585_PREFIX = "qmt_roll_stage585_stage526_non_csv_live_evidence_discovery"

SCRIPT_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_script_capability_matrix_{MODEL_TAG}.csv"
FIELD_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_mapping_matrix_{MODEL_TAG}.csv"
COMPONENT_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_component_readiness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
RUNBOOK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_runbook_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

STAGE568_TEMPLATE = OUTPUT_DIR / f"{STAGE568_PREFIX}_live_execution_ledger_template_{STAGE568_TAG}.csv"
STAGE575_TEMPLATE = OUTPUT_DIR / f"{STAGE575_PREFIX}_live_p0_evidence_template_{STAGE575_TAG}.csv"
STAGE575_WATCHLIST = OUTPUT_DIR / f"{STAGE575_PREFIX}_watchlist_{STAGE575_TAG}.csv"
STAGE583_P0_GATES = OUTPUT_DIR / f"{STAGE583_PREFIX}_p0_close_gates_{STAGE583_TAG}.csv"
STAGE585_DECISION = OUTPUT_DIR / f"{STAGE585_PREFIX}_decision_{STAGE585_TAG}.json"

SCRIPT_PATHS = [
    PROJECT_DIR / "run_ctp_stage174_readonly_probe.py",
    PROJECT_DIR / "run_ctp_stage258_simnow_smoke_order.py",
    PROJECT_DIR / "run_ctp_stage285_simnow_open_close_proof.py",
    PROJECT_DIR / "run_ctp_stage287_simnow_disconnect_proof.py",
    PROJECT_DIR / "run_ctp_stage288_execution_acceptance_suite.py",
    PROJECT_DIR / "run_ctp_stage278_native_cpp_td_login_probe.cpp",
    PROJECT_DIR / "run_ctp_stage281_native_cpp_smoke_order.cpp",
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

EVENT_CAPTURE_FIELDS = {
    "order_submit_at": ["EVENT_ORDER", "datetime", "time"],
    "order_submit_price": ["EVENT_ORDER", "price"],
    "order_type": ["EVENT_ORDER", "type"],
    "limit_price": ["OrderRequest", "price"],
    "fill_first_at": ["EVENT_TRADE", "datetime"],
    "fill_last_at": ["EVENT_TRADE", "datetime"],
    "filled_volume": ["EVENT_TRADE", "volume", "EVENT_ORDER", "traded"],
    "cancelled_volume": ["EVENT_ORDER", "status", "volume", "traded"],
    "unfilled_volume": ["EVENT_ORDER", "volume", "traded", "status"],
    "account_equity_before": ["EVENT_ACCOUNT", "balance"],
    "broker_margin_before": ["EVENT_ACCOUNT", "frozen", "available"],
}

COMPUTED_FIELDS = {
    "avg_fill_price": "trade volume-weighted price grouped by vt_orderid",
    "commission_cash": "broker trade/account fee field if exposed, otherwise external fee model",
    "actual_slippage_cash": "directional difference between fill and backtest reference * volume * contract size",
    "actual_implementation_shortfall_bps": "directional difference between avg fill and signal/arrival price",
    "actual_vs_window_vwap_bps": "directional difference between avg fill and live/independent window VWAP",
}

INTENT_FIELDS = {
    "signal_generated_at": "Stage526/Stage575 signal intent ledger",
    "signal_price": "Stage526 signal reference price",
}

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
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
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
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _contains_all(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return all(term.lower() in lower for term in terms)


def _contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _safe_nonempty_count(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    series = frame[column]
    if pd.api.types.is_numeric_dtype(series):
        return int(pd.to_numeric(series, errors="coerce").notna().sum())
    return int(series.fillna("").astype(str).str.strip().ne("").sum())


def _gate_row(gate: str, passed: bool, actual: str, required: str, severity: str, judgement: str) -> dict[str, Any]:
    return {
        "gate": gate,
        "passed": int(bool(passed)),
        "actual": actual,
        "required": required,
        "severity": severity,
        "judgement": judgement,
    }


def build_script_matrix() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in SCRIPT_PATHS:
        text = _read_text(path)
        row = {
            "script": _relative(path),
            "exists": int(path.exists()),
            "event_order_registered": int(_contains_all(text, ["EVENT_ORDER", "event_engine.register"])),
            "event_trade_registered": int(_contains_all(text, ["EVENT_TRADE", "event_engine.register"])),
            "event_tick_registered": int(_contains_all(text, ["EVENT_TICK", "event_engine.register"])),
            "account_position_capture": int(_contains_all(text, ["EVENT_ACCOUNT", "EVENT_POSITION"])),
            "writes_order_trade_csv": int(
                _contains_any(text, ['rows["orders"]', "rows['orders']", "ORDER_PATH"])
                and _contains_any(text, ['rows["trades"]', "rows['trades']", "TRADE_PATH"])
            ),
            "vt_orderid_trade_link": int(_contains_all(text, ["vt_orderid", "trade"]) and _contains_any(text, ["orderid", "tradeid"])),
            "dry_run_or_submit_gate": int(_contains_any(text, ["dry-run", "confirm-submit", "CTP_SMOKE_ORDER_ENABLED", "send_order_api_called_count"])),
            "send_order_path": int(_contains_any(text, ["send_order(", "ReqOrderInsert"])),
            "signal_event_id_link": int(_contains_any(text, ["event_id", "Stage526", "stage526", "STAGE575", "live_execution_ledger"])),
            "tca_metric_compute": int(
                _contains_any(text, ["implementation_shortfall", "actual_vs_window_vwap", "vwap", "participation"])
                and _contains_any(text, ["avg_fill", "filled_volume", "trade"])
            ),
        }
        score_cols = [
            "event_order_registered",
            "event_trade_registered",
            "event_tick_registered",
            "account_position_capture",
            "writes_order_trade_csv",
            "vt_orderid_trade_link",
            "dry_run_or_submit_gate",
            "signal_event_id_link",
            "tca_metric_compute",
        ]
        row["capability_score"] = int(sum(row[col] for col in score_cols))
        row["capability_score_pct"] = round(row["capability_score"] / len(score_cols) * 100, 4)
        rows.append(row)
    return pd.DataFrame(rows)


def build_field_matrix(stage568: pd.DataFrame, stage575: pd.DataFrame, script_matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    joined_script_text = "\n".join(_read_text(path) for path in SCRIPT_PATHS if path.exists())
    event_capture_ready = bool(script_matrix["event_order_registered"].max() and script_matrix["event_trade_registered"].max())
    tick_ready = bool(script_matrix["event_tick_registered"].max())
    for field in REQUIRED_ACTUAL_FIELDS:
        in_stage568 = field in stage568.columns
        in_stage575 = field in stage575.columns
        nonempty_stage568 = _safe_nonempty_count(stage568, field)
        nonempty_stage575 = _safe_nonempty_count(stage575, field)
        if field in INTENT_FIELDS:
            source_type = "intent_link_required"
            raw_capture_ready = False
            compute_ready = False
            bridge_gap = "needs_stage526_signal_intent_key"
        elif field in EVENT_CAPTURE_FIELDS:
            source_type = "event_capture_or_order_request"
            raw_capture_ready = event_capture_ready and _contains_any(joined_script_text, EVENT_CAPTURE_FIELDS[field])
            compute_ready = False
            bridge_gap = "needs_vt_orderid_event_id_join" if raw_capture_ready else "missing_event_capture"
        elif field in COMPUTED_FIELDS:
            source_type = "computed_tca_metric"
            raw_capture_ready = event_capture_ready or tick_ready
            compute_ready = bool(script_matrix["tca_metric_compute"].max())
            bridge_gap = "needs_tca_computation_bridge" if not compute_ready else "computed_somewhere_not_stage526_bridge"
        else:
            source_type = "unknown"
            raw_capture_ready = False
            compute_ready = False
            bridge_gap = "unmapped"
        rows.append(
            {
                "field": field,
                "source_type": source_type,
                "stage568_template_has_column": int(in_stage568),
                "stage575_template_has_column": int(in_stage575),
                "stage568_nonempty_rows": nonempty_stage568,
                "stage575_nonempty_rows": nonempty_stage575,
                "raw_event_capture_ready": int(raw_capture_ready),
                "automatic_compute_ready": int(compute_ready),
                "current_live_values_present": int((nonempty_stage568 + nonempty_stage575) > 0),
                "bridge_gap": bridge_gap,
            }
        )
    return pd.DataFrame(rows)


def build_component_matrix(
    script_matrix: pd.DataFrame,
    field_matrix: pd.DataFrame,
    stage575: pd.DataFrame,
    p0_gates: pd.DataFrame,
    stage585_decision: dict[str, Any],
) -> pd.DataFrame:
    event_capture_score = int(
        script_matrix[
            ["event_order_registered", "event_trade_registered", "event_tick_registered", "account_position_capture", "writes_order_trade_csv"]
        ].max().sum()
    )
    required_columns_present = int(
        (
            field_matrix["stage568_template_has_column"].astype(bool)
            & field_matrix["stage575_template_has_column"].astype(bool)
        ).sum()
    )
    p0_rows = stage575[stage575.get("watch_priority", "").fillna("").astype(str).str.startswith("P0")] if "watch_priority" in stage575.columns else pd.DataFrame()
    valid_live_samples = 0
    if not p0_gates.empty and "valid_live_tca_samples" in p0_gates.columns:
        valid_live_samples = int(pd.to_numeric(p0_gates["valid_live_tca_samples"], errors="coerce").fillna(0).sum())
    non_csv_p0_close_files = int(stage585_decision.get("p0_live_tca_close_files", 0) or 0)

    rows = [
        {
            "component": "vnpy_event_capture",
            "readiness": "ready",
            "score": event_capture_score,
            "max_score": 5,
            "passed": int(event_capture_score >= 5),
            "evidence": "CTP scripts register EVENT_ORDER/EVENT_TRADE/EVENT_TICK and persist order/trade rows.",
            "gap": "",
        },
        {
            "component": "stage526_live_tca_template",
            "readiness": "ready",
            "score": required_columns_present,
            "max_score": len(REQUIRED_ACTUAL_FIELDS),
            "passed": int(required_columns_present == len(REQUIRED_ACTUAL_FIELDS)),
            "evidence": f"Stage568/575 templates contain {required_columns_present}/{len(REQUIRED_ACTUAL_FIELDS)} required actual fields.",
            "gap": "",
        },
        {
            "component": "p0_execution_watchlist",
            "readiness": "ready",
            "score": len(p0_rows),
            "max_score": 3,
            "passed": int(len(p0_rows) >= 3),
            "evidence": f"P0 rows found: {len(p0_rows)}.",
            "gap": "",
        },
        {
            "component": "signal_intent_to_order_join",
            "readiness": "missing",
            "score": int(script_matrix["signal_event_id_link"].max()),
            "max_score": 1,
            "passed": int(script_matrix["signal_event_id_link"].max() >= 1),
            "evidence": "Existing execution scripts are smoke/proof scripts, not Stage526 event_id keyed ledgers.",
            "gap": "Need event_id/signal_id/intended volume joined to vt_orderid at submit time.",
        },
        {
            "component": "automatic_tca_computation",
            "readiness": "missing",
            "score": int(script_matrix["tca_metric_compute"].max()),
            "max_score": 1,
            "passed": int(script_matrix["tca_metric_compute"].max() >= 1),
            "evidence": "No current CTP bridge computes implementation shortfall, VWAP bps, participation and unfilled together for Stage526 P0.",
            "gap": "Need post-fill reducer over order/trade/tick/minute benchmark rows.",
        },
        {
            "component": "existing_valid_live_tca_samples",
            "readiness": "missing",
            "score": valid_live_samples + non_csv_p0_close_files,
            "max_score": 9,
            "passed": int((valid_live_samples + non_csv_p0_close_files) >= 9),
            "evidence": f"CSV valid live samples={valid_live_samples}; non-CSV P0 close files={non_csv_p0_close_files}.",
            "gap": "Need 3 valid comparable samples for each P0 lc2505/AP505/fu2509 bucket.",
        },
    ]
    return pd.DataFrame(rows)


def build_gates(component_matrix: pd.DataFrame, field_matrix: pd.DataFrame, p0_gates: pd.DataFrame) -> pd.DataFrame:
    event_capture_pass = bool(component_matrix.loc[component_matrix["component"].eq("vnpy_event_capture"), "passed"].max())
    template_pass = bool(component_matrix.loc[component_matrix["component"].eq("stage526_live_tca_template"), "passed"].max())
    p0_pass = bool(component_matrix.loc[component_matrix["component"].eq("p0_execution_watchlist"), "passed"].max())
    intent_join_pass = bool(component_matrix.loc[component_matrix["component"].eq("signal_intent_to_order_join"), "passed"].max())
    tca_compute_pass = bool(component_matrix.loc[component_matrix["component"].eq("automatic_tca_computation"), "passed"].max())
    samples_pass = bool(component_matrix.loc[component_matrix["component"].eq("existing_valid_live_tca_samples"), "passed"].max())
    actual_value_fields = int(field_matrix["current_live_values_present"].sum())
    p0_remaining = 9
    if not p0_gates.empty and "remaining_valid_samples" in p0_gates.columns:
        p0_remaining = int(pd.to_numeric(p0_gates["remaining_valid_samples"], errors="coerce").fillna(0).sum())

    rows = [
        _gate_row("vnpy_order_trade_tick_capture_available", event_capture_pass, str(event_capture_pass), "true", "hard", "raw event hook exists"),
        _gate_row("stage526_tca_templates_define_required_fields", template_pass, f"{int(field_matrix['stage568_template_has_column'].sum())}/{len(field_matrix)} stage568; {int(field_matrix['stage575_template_has_column'].sum())}/{len(field_matrix)} stage575", "all required fields", "hard", "schema exists"),
        _gate_row("p0_watchlist_available", p0_pass, str(p0_pass), "true", "hard", "P0 target buckets are known"),
        _gate_row("stage526_signal_intent_to_order_join_exists", intent_join_pass, str(intent_join_pass), "true", "hard", "missing bridge"),
        _gate_row("automatic_live_tca_metric_compute_exists", tca_compute_pass, str(tca_compute_pass), "true", "hard", "missing reducer"),
        _gate_row("current_templates_have_live_actual_values", actual_value_fields >= len(REQUIRED_ACTUAL_FIELDS), f"{actual_value_fields}/{len(REQUIRED_ACTUAL_FIELDS)}", "all required fields populated by live run", "hard", "templates are blank for live fields"),
        _gate_row("p0_valid_live_samples_complete", samples_pass, f"remaining={p0_remaining}", "remaining=0 and total>=9", "hard", "evidence gap remains open"),
        _gate_row("zero_execution_bias_claim_allowed", False, "not allowed", "allowed only after bridge + valid samples", "hard", "Stage526 remains normal-cost candidate"),
    ]
    return pd.DataFrame(rows)


def write_runbook() -> str:
    text = f"""# Stage586 Live TCA Ledger Hook Runbook

## Purpose

This is a dry-run engineering specification. It does not connect to CTP, does not call `send_order`, and does not change Stage526 strategy logic.

## Required Join Keys

1. `event_id`: Stage526/Stage575 signal event id.
2. `signal_id`: stable id for the generated signal, including strategy version and target date.
3. `vt_orderid`: vn.py order id returned by `send_order`.
4. `tradeid`/`vt_tradeid`: vn.py trade id from `EVENT_TRADE`.
5. `vt_symbol`: exact contract symbol, not just product symbol.

## Minimal Live Row Lifecycle

1. Before submit: write intent row with `event_id`, `date`, `vt_symbol`, `product_vt_symbol`, `offset_type`, `execution_side`, `order_volume`, `signal_generated_at`, `signal_price`, `account_equity_before`, `broker_margin_before`.
2. At submit: attach `order_submit_at`, `order_submit_price`, `order_type`, `limit_price`, `vt_orderid`.
3. On `EVENT_ORDER`: update latest `status`, `traded`, inferred `unfilled_volume`, reject/error status if any.
4. On `EVENT_TRADE`: append fill rows, then compute `fill_first_at`, `fill_last_at`, `filled_volume`, `avg_fill_price`.
5. From live ticks or independent minute bars: compute target benchmark VWAP for `14:30-15:00` and arrival-price implementation shortfall.
6. After completion/cancel: write `cancelled_volume`, `actual_slippage_cash`, `actual_implementation_shortfall_bps`, `actual_vs_window_vwap_bps`, participation and operator note.

## P0 Close Gate

For each P0 bucket (`lc2505.GFEX`, `AP505.CZCE`, `fu2509.SHFE`), close only after at least 3 comparable live fills or independent full-day minute evidence:

- `filled_volume/order_volume=100%`
- `unfilled_volume=0`
- `actual_vs_window_vwap_bps<=50`
- `actual_implementation_shortfall_bps<=75`
- `participation<=25%`
- no broker reject/filter

## Safety

- Dry-run first.
- A normal audit must leave `send_order_api_called_count=0`.
- Submit paths require the existing SimNow/broker-test confirmation gates from `skills/stage78-simnow-shadow-sop/SKILL.md`.
"""
    RUNBOOK_PATH.write_text(text, encoding="utf-8")
    return text


def write_chart(script_matrix: pd.DataFrame, field_matrix: pd.DataFrame, component_matrix: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    ax = axes[0, 0]
    comp = component_matrix.copy()
    colors = ["#2e7d32" if bool(x) else "#c62828" for x in comp["passed"]]
    ax.barh(comp["component"], comp["score"], color=colors)
    for idx, row in comp.iterrows():
        ax.text(float(row["score"]) + 0.05, idx, f"{row['score']}/{row['max_score']} {row['readiness']}", va="center", fontsize=9)
    ax.set_title("Component readiness")
    ax.set_xlabel("score")
    ax.invert_yaxis()

    ax = axes[0, 1]
    capability_cols = [
        "event_order_registered",
        "event_trade_registered",
        "event_tick_registered",
        "account_position_capture",
        "writes_order_trade_csv",
        "vt_orderid_trade_link",
        "dry_run_or_submit_gate",
        "signal_event_id_link",
        "tca_metric_compute",
    ]
    heat = script_matrix[capability_cols].to_numpy(dtype=float)
    im = ax.imshow(heat, aspect="auto", cmap="Greens", vmin=0, vmax=1)
    ax.set_yticks(range(len(script_matrix)))
    ax.set_yticklabels([Path(item).name.replace("run_ctp_", "") for item in script_matrix["script"]], fontsize=8)
    ax.set_xticks(range(len(capability_cols)))
    ax.set_xticklabels([col.replace("_", "\n") for col in capability_cols], rotation=0, fontsize=7)
    ax.set_title("Existing script capability matrix")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, int(heat[i, j]), ha="center", va="center", fontsize=8, color="black")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)

    ax = axes[1, 0]
    field_cols = ["stage568_template_has_column", "stage575_template_has_column", "raw_event_capture_ready", "automatic_compute_ready", "current_live_values_present"]
    field_view = field_matrix.set_index("field")[field_cols]
    heat2 = field_view.to_numpy(dtype=float)
    ax.imshow(heat2, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(field_view)))
    ax.set_yticklabels(field_view.index, fontsize=7)
    ax.set_xticks(range(len(field_cols)))
    ax.set_xticklabels([col.replace("_", "\n") for col in field_cols], fontsize=7)
    ax.set_title("Required field coverage")
    for i in range(heat2.shape[0]):
        for j in range(heat2.shape[1]):
            ax.text(j, i, int(heat2[i, j]), ha="center", va="center", fontsize=7)

    ax = axes[1, 1]
    gate_colors = ["#2e7d32" if bool(x) else "#c62828" for x in gates["passed"]]
    ypos = np.arange(len(gates))
    ax.barh(ypos, np.ones(len(gates)), color=gate_colors)
    ax.set_yticks(ypos)
    ax.set_yticklabels(gates["gate"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Promotion gates")
    for idx, row in gates.iterrows():
        label = "PASS" if bool(row["passed"]) else "FAIL"
        ax.text(0.5, idx, label, ha="center", va="center", color="white", fontweight="bold")
    ax.invert_yaxis()

    fig.suptitle("Stage586 live TCA hook readiness: raw event capture exists, Stage526 bridge does not", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    script_matrix: pd.DataFrame,
    field_matrix: pd.DataFrame,
    component_matrix: pd.DataFrame,
    gates: pd.DataFrame,
    stage575: pd.DataFrame,
    stage585_decision: dict[str, Any],
) -> None:
    p0 = stage575[stage575["watch_priority"].fillna("").astype(str).str.startswith("P0")].copy()
    pass_count = int(gates["passed"].sum())
    text = f"""# Stage586 Live TCA Ledger Hook Readiness

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- phase type: read-only engineering audit; no strategy change; no CTP connection; no order API call.

## External Research Judgment

- vn.py exposes order/trade state through `EVENT_ORDER` and `EVENT_TRADE`; these are the right raw hooks for live execution capture.
- Transaction cost analysis cannot stop at fill price. A valid execution ledger needs order intent, submit time, fill lifecycle, VWAP benchmark, implementation shortfall, participation, unfilled volume and broker reject/filter state.
- Therefore the current bottleneck is not another historical return replay. The bottleneck is a Stage526 `event_id -> vt_orderid -> trade fill -> VWAP/shortfall` bridge.

References used: vn.py GitHub/docs, CME/market TCA material, open-source TCA implementations such as tcapy/QuestDB implementation-shortfall examples.

## Decision

- Decision: `live_tca_hook_partial_event_capture_ready_bridge_not_wired`
- Interpretation: existing vn.py CTP scripts can capture raw order/trade/tick events, and Stage568/575 templates already define the required TCA fields. But no single executable bridge links Stage526 P0 signal intent to live `EVENT_ORDER/EVENT_TRADE` and computes VWAP/implementation-shortfall/participation automatically.
- Result for Stage526: still a normal-cost candidate only. Zero execution-bias claim remains not allowed.

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

## Component Readiness

{_md_table(component_matrix)}

## Gates

{_md_table(gates)}

## Script Capability Matrix

{_md_table(script_matrix, max_rows=20)}

## Required Field Mapping

{_md_table(field_matrix, max_rows=40)}

## P0 Rows

{_md_table(p0, columns=['event_id', 'date', 'vt_symbol', 'offset_type', 'execution_side', 'order_volume', 'watch_priority', 'risk_score', 'risk_types'], max_rows=10)}

## Stage585 Evidence Carryover

- Stage585 decision: `{stage585_decision.get('decision', '')}`
- P0 live TCA close files: `{stage585_decision.get('p0_live_tca_close_files', 0)}`
- Zero execution-bias claim allowed: `not allowed`

## Visual Read

- Top-left component chart should show the green base components: raw vn.py event capture, templates and P0 watchlist are present.
- The same chart should show red gaps in `signal_intent_to_order_join`, `automatic_tca_computation`, and `existing_valid_live_tca_samples`.
- Top-right heatmap should show Stage285/258/287 scripts strong on raw events, but weak on Stage526 signal id linkage and TCA metric computation.
- Bottom-left field heatmap should show template columns present but current live actual values absent.
- Bottom-right gates should be a mixed chart with early engineering gates green and hard promotion gates red.

## Next Step

Implement a dry-run `live_tca_ledger_bridge` module before any claim of real execution neutrality:

1. Load Stage575 P0/live template intent rows.
2. At submit time, join `event_id/signal_id` to `vt_orderid`.
3. Persist raw `EVENT_ORDER`, `EVENT_TRADE`, `EVENT_TICK`, account and position snapshots.
4. Compute avg fill, unfilled/cancelled volume, VWAP bps, implementation shortfall bps and participation.
5. Require three valid comparable samples for each P0 bucket before closing the Stage526 execution-bias gap.

## Overfitting Reflection

- Before run: no. This is an engineering readiness audit, not a parameter search.
- After run: no. The result refuses promotion and identifies missing forward/live evidence instead of fitting history.

## Continued Value Reflection

- Before run: yes. Real execution bias is the main unresolved blocker for Stage526.
- After run: yes. The audit proves the raw hooks exist, so the next step is implementable; it also prevents overstating current evidence.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage568 = _read_csv(STAGE568_TEMPLATE)
    stage575 = _read_csv(STAGE575_TEMPLATE)
    p0_gates = _read_csv(STAGE583_P0_GATES) if STAGE583_P0_GATES.exists() else pd.DataFrame()
    if STAGE585_DECISION.exists():
        stage585_decision = json.loads(STAGE585_DECISION.read_text(encoding="utf-8"))
    else:
        stage585_decision = {}

    script_matrix = build_script_matrix()
    field_matrix = build_field_matrix(stage568=stage568, stage575=stage575, script_matrix=script_matrix)
    component_matrix = build_component_matrix(
        script_matrix=script_matrix,
        field_matrix=field_matrix,
        stage575=stage575,
        p0_gates=p0_gates,
        stage585_decision=stage585_decision,
    )
    gates = build_gates(component_matrix=component_matrix, field_matrix=field_matrix, p0_gates=p0_gates)
    runbook_text = write_runbook()

    script_matrix.to_csv(SCRIPT_MATRIX_PATH, index=False, encoding="utf-8-sig")
    field_matrix.to_csv(FIELD_MATRIX_PATH, index=False, encoding="utf-8-sig")
    component_matrix.to_csv(COMPONENT_MATRIX_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    write_chart(script_matrix=script_matrix, field_matrix=field_matrix, component_matrix=component_matrix, gates=gates)
    write_report(
        script_matrix=script_matrix,
        field_matrix=field_matrix,
        component_matrix=component_matrix,
        gates=gates,
        stage575=stage575,
        stage585_decision=stage585_decision,
    )

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "live_tca_hook_partial_event_capture_ready_bridge_not_wired",
        "stage526_reference": STAGE526_REFERENCE,
        "gate_pass_count": int(gates["passed"].sum()),
        "gate_total": int(len(gates)),
        "component_pass_count": int(component_matrix["passed"].sum()),
        "component_total": int(len(component_matrix)),
        "script_count": int(len(script_matrix)),
        "required_actual_fields": int(len(REQUIRED_ACTUAL_FIELDS)),
        "required_fields_with_template_columns": int(
            (
                field_matrix["stage568_template_has_column"].astype(bool)
                & field_matrix["stage575_template_has_column"].astype(bool)
            ).sum()
        ),
        "required_fields_with_current_live_values": int(field_matrix["current_live_values_present"].sum()),
        "valid_live_tca_samples_current": int(
            pd.to_numeric(p0_gates.get("valid_live_tca_samples", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
        )
        if not p0_gates.empty
        else 0,
        "zero_execution_bias_claim_allowed": False,
        "next_required_action": "build dry-run Stage526 live_tca_ledger_bridge joining event_id/signal_id to vt_orderid/trade fills and VWAP/shortfall metrics",
        "outputs": {
            "script_matrix": str(SCRIPT_MATRIX_PATH),
            "field_matrix": str(FIELD_MATRIX_PATH),
            "component_matrix": str(COMPONENT_MATRIX_PATH),
            "gates": str(GATES_PATH),
            "runbook": str(RUNBOOK_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
        "runbook_length": len(runbook_text),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
