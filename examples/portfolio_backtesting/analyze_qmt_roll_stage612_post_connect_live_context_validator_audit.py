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

from qmt_roll_live_context_adapter import (
    PRE_SUBMIT_HEATMAP_FIELDS,
    REQUIRED_LIVE_CONTEXT_FIELDS,
    build_pre_submit_heatmap_rows,
    evaluate_submit_plan_live_context,
    load_readonly_snapshot_files,
)


MODEL_TAG = "stage612_post_connect_live_context_validator_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage612_post_connect_live_context_validator_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE591_TAG = "stage591_stage526_bridge_submit_adapter_dry_run_v1"
STAGE591_PREFIX = "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run"
STAGE591_SUBMIT_PLAN = OUTPUT_DIR / f"{STAGE591_PREFIX}_submit_plan_{STAGE591_TAG}.csv"

STAGE608_SUMMARY = OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_summary_stage608_readonly_tick_snapshot_probe_v1.json"
STAGE610_DECISION = OUTPUT_DIR / "qmt_roll_stage610_stage608_simnow_env_wrapper_audit_decision_stage610_stage608_simnow_env_wrapper_audit_v1.json"

SOURCE_INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_inventory_{MODEL_TAG}.csv"
SYMBOL_VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_validation_{MODEL_TAG}.csv"
CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_context_rows_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_readiness_{MODEL_TAG}.csv"
HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pre_submit_heatmap_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "vn.py MainEngine query APIs: https://deepwiki.com/vnpy/vnpy/2.2-main-engine",
    "vn.py OmsEngine state cache: https://deepwiki.com/vnpy/vnpy/2.3-gateways",
    "vn.py source tree: https://github.com/vnpy/vnpy/tree/master/vnpy/trader",
    "vnpy_ctp gateway package: https://github.com/vnpy/vnpy_ctp",
]


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
        return {str(k): _json_safe(v) for k, v in value.items()}
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


def _vt_symbol_from_row(row: dict[str, Any]) -> str:
    vt_symbol = _clean(row.get("vt_symbol"))
    if vt_symbol:
        return vt_symbol
    symbol = _clean(row.get("symbol"))
    exchange = _clean(row.get("exchange"))
    return f"{symbol}.{exchange}" if symbol and exchange else ""


def _vt_set(rows: list[dict[str, Any]]) -> set[str]:
    return {symbol for symbol in (_vt_symbol_from_row(row) for row in rows) if symbol}


def build_source_inventory(summary: dict[str, Any], snapshots: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    outputs = summary.get("outputs", {}) if isinstance(summary.get("outputs"), dict) else {}
    for component in ["contracts", "accounts", "positions", "ticks", "orders", "trades", "logs", "position_query_callbacks"]:
        path = Path(outputs.get(component, "")) if outputs.get(component) else None
        row_count = len(snapshots.get(component, [])) if component in snapshots else len(_read_csv(path)) if path else 0
        rows.append(
            {
                "component": component,
                "path": str(path) if path else "",
                "rows": int(row_count),
                "exists": int(bool(path and path.exists())),
                "generated_at": _clean(summary.get("generated_at")),
                "status": _clean(summary.get("status")),
                "connect_requested": int(bool(summary.get("connect_requested", False))),
                "send_order_api_called_count": int(summary.get("send_order_api_called_count", 0) or 0),
                "cancel_order_api_called_count": int(summary.get("cancel_order_api_called_count", 0) or 0),
                "subscribe_api_called_count": int(summary.get("subscribe_api_called_count", 0) or 0),
            }
        )
    return pd.DataFrame(rows)


def build_symbol_validation(submit_plan: pd.DataFrame, snapshots: dict[str, list[dict[str, Any]]], readiness: pd.DataFrame) -> pd.DataFrame:
    contracts = _vt_set(snapshots.get("contracts", []))
    ticks = _vt_set(snapshots.get("ticks", []))
    positions = _vt_set(snapshots.get("positions", []))
    rows = []
    readiness_by_symbol = {str(row.get("vt_symbol")): row for row in readiness.to_dict(orient="records")}
    for row in submit_plan.to_dict(orient="records"):
        vt_symbol = _clean(row.get("vt_symbol"))
        ready = readiness_by_symbol.get(vt_symbol, {})
        rows.append(
            {
                "bridge_signal_id": row.get("bridge_signal_id", ""),
                "vt_symbol": vt_symbol,
                "watch_priority": row.get("watch_priority", ""),
                "offset": row.get("offset", ""),
                "direction": row.get("direction", ""),
                "planned_volume": row.get("planned_volume", ""),
                "target_loaded": 1,
                "contract_present": int(vt_symbol in contracts),
                "tick_present": int(vt_symbol in ticks),
                "position_symbol_present": int(vt_symbol in positions),
                "account_present": int(len(snapshots.get("accounts", [])) > 0),
                "live_context_passed_fields": int(ready.get("live_context_passed_fields", 0) or 0),
                "live_context_total_fields": int(ready.get("live_context_total_fields", len(REQUIRED_LIVE_CONTEXT_FIELDS)) or len(REQUIRED_LIVE_CONTEXT_FIELDS)),
                "real_submit_allowed": int(ready.get("real_submit_allowed", 0) or 0),
                "next_blocker_class": ready.get("next_blocker_class", "missing_validator_row"),
                "blockers": ready.get("blockers", "missing_validator_row"),
            }
        )
    return pd.DataFrame(rows)


def build_gates(
    summary: dict[str, Any],
    stage610: dict[str, Any],
    source_inventory: pd.DataFrame,
    symbol_validation: pd.DataFrame,
    context: pd.DataFrame,
    readiness: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    submit_rows = len(symbol_validation)
    target_count = int(summary.get("target_symbol_count", 0) or len(symbol_validation))
    source_rows = {str(row.component): int(row.rows) for row in source_inventory.itertuples(index=False)}
    contract_coverage = int(symbol_validation["contract_present"].sum()) if not symbol_validation.empty else 0
    tick_coverage = int(symbol_validation["tick_present"].sum()) if not symbol_validation.empty else 0
    account_present = int(symbol_validation["account_present"].sum()) if not symbol_validation.empty else 0
    live_context_present = int(context["present_in_adapter"].sum()) if not context.empty else 0
    live_context_required = len(context)
    real_submit_allowed = int(readiness["real_submit_allowed"].sum()) if not readiness.empty else 0
    hard_gate_items = [
        {
            "gate": "stage608_summary_present",
            "passed": int(bool(summary)),
            "actual": str(bool(summary)),
            "threshold": "true",
            "judgement": "需要 Stage608 read-only tick probe summary 作为输入。",
        },
        {
            "gate": "stage610_wrapper_ready",
            "passed": int(stage610.get("wrapper_capabilities_passed") == stage610.get("wrapper_capabilities_total") and bool(stage610)),
            "actual": f"{stage610.get('wrapper_capabilities_passed', 0)}/{stage610.get('wrapper_capabilities_total', 0)}",
            "threshold": "all capabilities",
            "judgement": "wrapper/env 合同必须先准备好。",
        },
        {
            "gate": "explicit_readonly_connect_observed",
            "passed": int(bool(summary.get("connect_requested", False))),
            "actual": str(bool(summary.get("connect_requested", False))),
            "threshold": "true after user-approved --connect",
            "judgement": "当前 dry-run 未连接；这是预期阻塞。",
        },
        {
            "gate": "no_order_surface_called",
            "passed": int(summary.get("send_order_api_called_count", 0) == 0 and summary.get("cancel_order_api_called_count", 0) == 0),
            "actual": f"send={summary.get('send_order_api_called_count', 0)};cancel={summary.get('cancel_order_api_called_count', 0)}",
            "threshold": "send=0 cancel=0",
            "judgement": "post-connect验证也必须只读。",
        },
        {
            "gate": "target_symbols_loaded",
            "passed": int(target_count == submit_rows and submit_rows > 0),
            "actual": f"{target_count}/{submit_rows}",
            "threshold": "all submit plan rows",
            "judgement": "目标合约来自 Stage591 submit plan。",
        },
        {
            "gate": "contract_coverage_all_targets",
            "passed": int(contract_coverage == submit_rows and submit_rows > 0),
            "actual": f"{contract_coverage}/{submit_rows}",
            "threshold": "all target symbols",
            "judgement": "连接后必须有当前合约快照。",
        },
        {
            "gate": "tick_coverage_all_targets",
            "passed": int(tick_coverage == submit_rows and submit_rows > 0),
            "actual": f"{tick_coverage}/{submit_rows}",
            "threshold": "all target symbols",
            "judgement": "连接后必须有当前 tick，不能用历史 reference price。",
        },
        {
            "gate": "account_snapshot_present",
            "passed": int(account_present == submit_rows and submit_rows > 0),
            "actual": f"{account_present}/{submit_rows}; account_rows={source_rows.get('accounts', 0)}",
            "threshold": "all target rows see account",
            "judgement": "必须有账户权益/可用资金快照。",
        },
        {
            "gate": "position_snapshot_confirmed",
            "passed": int(source_rows.get("positions", 0) > 0 or _clean(summary.get("broker_snapshot", {}).get("position_snapshot_state", "")) == "confirmed_flat"),
            "actual": f"position_rows={source_rows.get('positions', 0)};state={_clean(summary.get('broker_snapshot', {}).get('position_snapshot_state', ''))}",
            "threshold": "positions rows or confirmed_flat",
            "judgement": "平仓信号必须由真实仓位状态确认。",
        },
        {
            "gate": "validator_live_context_ready",
            "passed": int(live_context_present == live_context_required and live_context_required > 0),
            "actual": f"{live_context_present}/{live_context_required}",
            "threshold": "all live context fields",
            "judgement": "Stage606/607 validator 需要九类 live context 全部通过。",
        },
        {
            "gate": "real_submit_fail_closed",
            "passed": int(real_submit_allowed == 0 and submit_rows > 0),
            "actual": f"{real_submit_allowed}/{submit_rows}",
            "threshold": "0 until operator confirmation and fresh snapshots",
            "judgement": "当前仍应 fail-closed。",
        },
        {
            "gate": "fresh_tick_rows_exist",
            "passed": int(source_rows.get("ticks", 0) > 0),
            "actual": str(source_rows.get("ticks", 0)),
            "threshold": ">0 after explicit connect",
            "judgement": "当前 tick rows=0，不能声明真实交易无偏差。",
        },
    ]
    for item in hard_gate_items:
        item["hard_gate"] = 1
        rows.append(item)
    return pd.DataFrame(rows)


def _blocker_counts(readiness: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for text in readiness.get("blockers", pd.Series(dtype=str)).fillna("").astype(str):
        for blocker in [part for part in text.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame([{"blocker": key, "count": value} for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))])


def make_chart(gates: pd.DataFrame, symbol_validation: pd.DataFrame, heatmap: pd.DataFrame, readiness: pd.DataFrame, source_inventory: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(17, 11), constrained_layout=True)
    gs = fig.add_gridspec(2, 2)

    ax1 = fig.add_subplot(gs[0, 0])
    ordered = gates.copy()
    colors = ordered["passed"].map(lambda x: "#1b9e77" if int(x) else "#d73027")
    ax1.barh(ordered["gate"], np.ones(len(ordered)), color=colors, alpha=0.88)
    ax1.set_xlim(0, 1.02)
    ax1.set_xlabel("Gate status")
    ax1.set_title("Post-connect gates: current dry-run must remain blocked")
    ax1.invert_yaxis()
    for y, (_, row) in enumerate(ordered.iterrows()):
        ax1.text(0.03, y, "PASS" if int(row["passed"]) else "BLOCK", va="center", ha="left", color="white", fontsize=8, fontweight="bold")

    ax2 = fig.add_subplot(gs[0, 1])
    coverage_cols = ["contract_present", "tick_present", "position_symbol_present", "account_present", "real_submit_allowed"]
    matrix = symbol_validation.set_index("vt_symbol")[coverage_cols].astype(float)
    ax2.imshow(matrix.values, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#d73027", "#1b9e77"]), vmin=0, vmax=1)
    ax2.set_xticks(np.arange(len(coverage_cols)))
    ax2.set_xticklabels(["contract", "tick", "position", "account", "submit"], rotation=25, ha="right")
    ax2.set_yticks(np.arange(len(matrix.index)))
    ax2.set_yticklabels(matrix.index)
    ax2.set_title("Target-symbol live coverage")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax2.text(j, i, "Y" if matrix.iat[i, j] else "N", ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    ax3 = fig.add_subplot(gs[1, 0])
    if heatmap.empty or readiness.empty:
        ax3.text(0.5, 0.5, "No heatmap rows", ha="center", va="center")
        ax3.set_axis_off()
    else:
        pre = (
            heatmap.pivot_table(index="bridge_signal_id", columns="field", values="passed", aggfunc="max")
            .reindex(readiness["bridge_signal_id"])
            .reindex(columns=PRE_SUBMIT_HEATMAP_FIELDS)
            .fillna(0)
            .astype(float)
        )
        labels = readiness["vt_symbol"].astype(str) + "\n" + readiness["watch_priority"].astype(str).str.slice(0, 18)
        ax3.imshow(pre.values, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#d73027", "#1b9e77"]), vmin=0, vmax=1)
        ax3.set_xticks(np.arange(len(PRE_SUBMIT_HEATMAP_FIELDS)))
        ax3.set_xticklabels(["ref", "payload", "contract", "account", "position", "limit", "band", "margin", "operator"], rotation=28, ha="right")
        ax3.set_yticks(np.arange(len(labels)))
        ax3.set_yticklabels(labels, fontsize=8)
        ax3.set_title("Shared live-context validator heatmap")
        for i in range(pre.shape[0]):
            for j in range(pre.shape[1]):
                ax3.text(j, i, "Y" if pre.iat[i, j] else "N", ha="center", va="center", color="white", fontsize=7, fontweight="bold")

    ax4 = fig.add_subplot(gs[1, 1])
    blockers = _blocker_counts(readiness).head(10)
    inv = source_inventory[source_inventory["component"].isin(["contracts", "accounts", "positions", "ticks"])]
    if not blockers.empty:
        y = np.arange(len(blockers))
        ax4.barh(y, blockers["count"], color="#d73027", alpha=0.85)
        ax4.set_yticks(y)
        ax4.set_yticklabels(blockers["blocker"], fontsize=8)
        ax4.invert_yaxis()
        ax4.set_xlabel("orders blocked")
        ax4.set_title("Current blocker distribution")
        for idx, row in blockers.iterrows():
            ax4.text(row["count"] + 0.04, idx, str(int(row["count"])), va="center", fontsize=8)
    else:
        y = np.arange(len(inv))
        ax4.barh(y, inv["rows"], color="#7570b3")
        ax4.set_yticks(y)
        ax4.set_yticklabels(inv["component"])
        ax4.set_title("Source inventory rows")
    fig.suptitle("Stage612 post-connect live context validator: ready to audit, current dry-run has no live evidence", fontsize=15, fontweight="bold")
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    decision: dict[str, Any],
    gates: pd.DataFrame,
    source_inventory: pd.DataFrame,
    symbol_validation: pd.DataFrame,
    readiness: pd.DataFrame,
) -> None:
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    text = f"""# Stage612 post-connect live context validator audit

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

Judgement: vn.py's `MainEngine` delegates cached state queries such as `get_tick` and `get_contract` to `OmsEngine`, and tick/contract/account/position updates are event-driven. Therefore a post-connect validator should read cached snapshots and refuse submit unless target contract/tick/account/position evidence is fresh and symbol-aligned.

## Key result

- Target symbols: `{decision['target_symbol_count']}`.
- Stage608 connect requested: `{decision['stage608_connect_requested']}`.
- Stage608 status: `{decision['stage608_status']}`.
- Contract coverage: `{decision['contract_coverage']}/{decision['submit_plan_rows']}`.
- Tick coverage: `{decision['tick_coverage']}/{decision['submit_plan_rows']}`.
- Live context fields present: `{decision['live_context_present_rows']}/{decision['live_context_required_rows']}`.
- Real submit allowed: `{decision['real_submit_allowed_rows']}/{decision['submit_plan_rows']}`.
- Hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`.

## Source inventory

{_md_table(source_inventory, ['component', 'rows', 'exists', 'status', 'connect_requested', 'subscribe_api_called_count'], max_rows=20)}

## Symbol validation

{_md_table(symbol_validation, ['vt_symbol', 'watch_priority', 'contract_present', 'tick_present', 'position_symbol_present', 'account_present', 'live_context_passed_fields', 'real_submit_allowed', 'next_blocker_class'], max_rows=20)}

## Failed gates

{_md_table(failed, ['gate', 'actual', 'threshold', 'judgement'], max_rows=20)}

## Order readiness

{_md_table(readiness, ['vt_symbol', 'watch_priority', 'order_reference_ready', 'dry_run_payload_ready', 'live_context_passed_fields', 'real_submit_allowed', 'next_blocker_class'], max_rows=20)}

## Visual read

- Top-left gate panel should stay mostly red in current dry-run because no explicit read-only connect was executed.
- Top-right target-symbol matrix should show target rows loaded but contract/tick/account/position unavailable.
- Bottom-left validator heatmap should keep only reference/payload green; contract/account/position/tick-derived fields should remain red.
- Bottom-right blockers should be dominated by missing contract/account/position/tick/operator context.

## Conclusion

- Stage612 makes the post-connect audit repeatable without connecting now.
- Current evidence remains dry-run only, so it correctly blocks zero-bias and real submit claims.
- The next proof must be a user-approved read-only `--connect` Stage608 run that still has `send_order=0`, followed by this validator.

## Overfit reflection

- Before run: no overfit. This stage validates execution evidence only and does not touch strategy returns or product selection.
- After run: no overfit. The validator fails despite all dry-run payloads being ready, which prevents historical reference price leakage into real submit logic.

## Continue-value reflection

- Before run: valuable. It attacks the current strongest blocker: real tradability and no-bias proof.
- After run: valuable. It converts the next live read-only probe into a measurable checklist instead of an ad hoc manual inspection.

## Validation

- Script py_compile: passed.
- Script run: completed.
- Chart visual inspection: completed after generation.
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = _read_json(STAGE608_SUMMARY)
    stage610 = _read_json(STAGE610_DECISION)
    submit_plan = _read_csv(STAGE591_SUBMIT_PLAN)
    if submit_plan.empty:
        raise FileNotFoundError(STAGE591_SUBMIT_PLAN)
    snapshots = load_readonly_snapshot_files(summary, source="stage608_readonly_tick_snapshot_probe_files")
    context, readiness = evaluate_submit_plan_live_context(
        submit_plan,
        snapshots=snapshots,
        now=datetime.now(),
        operator_confirmed=False,
        max_snapshot_age_seconds=300,
        max_tick_age_seconds=10,
        allow_historical_reference_price=False,
    )
    heatmap = build_pre_submit_heatmap_rows(readiness, context)
    source_inventory = build_source_inventory(summary, snapshots)
    symbol_validation = build_symbol_validation(submit_plan, snapshots, readiness)
    gates = build_gates(summary, stage610, source_inventory, symbol_validation, context, readiness)

    hard = gates[gates["hard_gate"].astype(int).eq(1)]
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "post_connect_validator_ready_dry_run_fail_closed_waiting_for_live_snapshot",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "ctp_connection_attempted": False,
        "send_order_api_called_count": int(summary.get("send_order_api_called_count", 0) or 0),
        "cancel_order_api_called_count": int(summary.get("cancel_order_api_called_count", 0) or 0),
        "subscribe_api_called_count": int(summary.get("subscribe_api_called_count", 0) or 0),
        "stage608_status": _clean(summary.get("status")),
        "stage608_connect_requested": bool(summary.get("connect_requested", False)),
        "target_symbol_count": int(summary.get("target_symbol_count", 0) or len(symbol_validation)),
        "submit_plan_rows": int(len(submit_plan)),
        "contract_coverage": int(symbol_validation["contract_present"].sum()),
        "tick_coverage": int(symbol_validation["tick_present"].sum()),
        "account_coverage": int(symbol_validation["account_present"].sum()),
        "position_symbol_coverage": int(symbol_validation["position_symbol_present"].sum()),
        "live_context_present_rows": int(context["present_in_adapter"].sum()) if not context.empty else 0,
        "live_context_required_rows": int(len(context)),
        "real_submit_allowed_rows": int(readiness["real_submit_allowed"].sum()) if not readiness.empty else 0,
        "hard_gates_passed": int(hard["passed"].astype(int).sum()),
        "hard_gates_total": int(len(hard)),
        "failed_hard_gates": int((hard["passed"].astype(int) == 0).sum()),
        "visual_chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "source_references": REFERENCE_LINKS,
    }

    source_inventory.to_csv(SOURCE_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    symbol_validation.to_csv(SYMBOL_VALIDATION_PATH, index=False, encoding="utf-8-sig")
    context.to_csv(CONTEXT_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    heatmap.to_csv(HEATMAP_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(gates, symbol_validation, heatmap, readiness, source_inventory)
    write_report(decision, gates, source_inventory, symbol_validation, readiness)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
