from __future__ import annotations

from datetime import datetime
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
    load_stage174_readonly_snapshot,
)


MODEL_TAG = "stage607_readonly_snapshot_bridge_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage607_readonly_snapshot_bridge_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE591_TAG = "stage591_stage526_bridge_submit_adapter_dry_run_v1"
STAGE591_PREFIX = "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run"
STAGE591_SUBMIT_PLAN = OUTPUT_DIR / f"{STAGE591_PREFIX}_submit_plan_{STAGE591_TAG}.csv"

STAGE174_SUMMARY = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"

SNAPSHOT_INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_snapshot_inventory_{MODEL_TAG}.csv"
SYMBOL_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_coverage_{MODEL_TAG}.csv"
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
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def _parse_datetime(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _age_seconds(value: Any, now: datetime) -> float | None:
    dt = _parse_datetime(value)
    if dt is None:
        return None
    return round((now - dt).total_seconds(), 3)


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


def _vt_set(rows: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        vt_symbol = _clean(row.get("vt_symbol"))
        if not vt_symbol:
            symbol = _clean(row.get("symbol"))
            exchange = _clean(row.get("exchange"))
            vt_symbol = f"{symbol}.{exchange}" if symbol and exchange else ""
        if vt_symbol:
            values.add(vt_symbol)
    return values


def build_snapshot_inventory(summary: dict[str, Any], snapshots: dict[str, list[dict[str, Any]]], now: datetime) -> pd.DataFrame:
    generated_at = _clean(summary.get("generated_at"))
    age = _age_seconds(generated_at, now)
    rows = []
    for name in ["contracts", "accounts", "positions", "ticks"]:
        rows.append(
            {
                "snapshot_component": name,
                "rows": int(len(snapshots.get(name, []))),
                "generated_at": generated_at,
                "age_seconds": age if age is not None else np.nan,
                "fresh_300s": int(age is not None and age <= 300),
                "source_status": _clean(summary.get("status")),
            }
        )
    broker = summary.get("broker_snapshot", {}) if isinstance(summary.get("broker_snapshot", {}), dict) else {}
    rows.append(
        {
            "snapshot_component": "broker_snapshot",
            "rows": int(broker.get("position_rows", 0) or 0),
            "generated_at": generated_at,
            "age_seconds": age if age is not None else np.nan,
            "fresh_300s": int(age is not None and age <= 300),
            "source_status": _clean(broker.get("position_snapshot_state")),
        }
    )
    return pd.DataFrame(rows)


def build_symbol_coverage(submit_plan: pd.DataFrame, snapshots: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    contract_symbols = _vt_set(snapshots.get("contracts", []))
    position_symbols = _vt_set(snapshots.get("positions", []))
    tick_symbols = _vt_set(snapshots.get("ticks", []))
    rows = []
    for row in submit_plan.to_dict(orient="records"):
        vt_symbol = _clean(row.get("vt_symbol"))
        rows.append(
            {
                "bridge_signal_id": row.get("bridge_signal_id"),
                "vt_symbol": vt_symbol,
                "watch_priority": row.get("watch_priority"),
                "contract_in_snapshot": int(vt_symbol in contract_symbols),
                "position_symbol_in_snapshot": int(vt_symbol in position_symbols),
                "tick_in_snapshot": int(vt_symbol in tick_symbols),
                "snapshot_coverage_status": (
                    "contract_tick_position_ready"
                    if vt_symbol in contract_symbols and vt_symbol in tick_symbols and vt_symbol in position_symbols
                    else "missing_" + ",".join(
                        part
                        for part, ok in [
                            ("contract", vt_symbol in contract_symbols),
                            ("tick", vt_symbol in tick_symbols),
                            ("position", vt_symbol in position_symbols),
                        ]
                        if not ok
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def build_gates(
    summary: dict[str, Any],
    inventory: pd.DataFrame,
    coverage: pd.DataFrame,
    context: pd.DataFrame,
    readiness: pd.DataFrame,
) -> pd.DataFrame:
    summary_exists = bool(summary)
    status = _clean(summary.get("status"))
    contract_rows = int(inventory.loc[inventory["snapshot_component"].eq("contracts"), "rows"].iloc[0]) if not inventory.empty else 0
    account_rows = int(inventory.loc[inventory["snapshot_component"].eq("accounts"), "rows"].iloc[0]) if not inventory.empty else 0
    position_rows = int(inventory.loc[inventory["snapshot_component"].eq("positions"), "rows"].iloc[0]) if not inventory.empty else 0
    tick_rows = int(inventory.loc[inventory["snapshot_component"].eq("ticks"), "rows"].iloc[0]) if not inventory.empty else 0
    fresh_components = int(inventory["fresh_300s"].sum()) if not inventory.empty else 0
    contract_coverage = int(coverage["contract_in_snapshot"].sum()) if not coverage.empty else 0
    tick_coverage = int(coverage["tick_in_snapshot"].sum()) if not coverage.empty else 0
    context_present = int(context["present_in_adapter"].sum()) if not context.empty else 0
    context_required = int(len(context))
    real_submit = int(readiness["real_submit_allowed"].sum()) if not readiness.empty else 0
    row_count = int(len(readiness))
    rows = [
        ("stage174_summary_found", summary_exists, str(summary_exists), "True", "hard", "Need a persisted read-only probe summary."),
        ("stage174_status_snapshot_received", status == "readonly_snapshots_received", status, "readonly_snapshots_received", "hard", "Read-only probe must have account/position snapshots."),
        ("no_ctp_connection_attempted_stage607", True, "False", "False", "hard", "Stage607 only reads existing files."),
        ("no_send_order_api_called_stage607", True, "0", "0", "hard", "Stage607 must not call broker APIs."),
        ("contracts_file_nonempty", contract_rows > 0, str(contract_rows), ">0", "hard", "Contract file must exist before mapping symbols."),
        ("accounts_file_nonempty", account_rows > 0, str(account_rows), ">0", "hard", "Account file must exist before account equity/margin checks."),
        ("positions_file_nonempty_or_confirmed_flat", position_rows > 0 or _clean(summary.get("broker_snapshot", {}).get("position_snapshot_state", "")) == "confirmed_flat", str(position_rows), ">0 or confirmed_flat", "hard", "Need position snapshot state before close orders."),
        ("ticks_available", tick_rows > 0, str(tick_rows), ">0", "hard", "Live limit price requires tick rows."),
        ("snapshot_fresh_300s", fresh_components == len(inventory) and not inventory.empty, f"{fresh_components}/{len(inventory)}", "all components", "hard", "Existing file snapshot must be fresh to pass."),
        ("stage591_contract_coverage", contract_coverage == row_count and row_count > 0, f"{contract_coverage}/{row_count}", "all Stage591 rows", "hard", "Snapshot contracts must match submit plan vt_symbols."),
        ("stage591_tick_coverage", tick_coverage == row_count and row_count > 0, f"{tick_coverage}/{row_count}", "all Stage591 rows", "hard", "Snapshot ticks must match submit plan vt_symbols."),
        ("validator_context_ready", context_present == context_required and context_required > 0, f"{context_present}/{context_required}", "all live context fields", "hard", "Validator should only pass with fresh matching live context."),
        ("real_submit_still_blocked", real_submit == 0 and row_count > 0, f"{real_submit}/{row_count}", "0 until operator confirmation and current snapshots", "hard", "Bridge audit should remain dry-run blocked."),
    ]
    return pd.DataFrame(
        [
            {
                "gate": name,
                "passed": int(bool(passed)),
                "observed": observed,
                "required": required,
                "severity": severity,
                "rationale": rationale,
            }
            for name, passed, observed, required, severity, rationale in rows
        ]
    )


def plot_chart(
    inventory: pd.DataFrame,
    coverage: pd.DataFrame,
    heatmap: pd.DataFrame,
    readiness: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Stage607 read-only snapshot bridge audit: file snapshot exists, but stale and not symbol-aligned", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    view = inventory[inventory["snapshot_component"].isin(["contracts", "accounts", "positions", "ticks"])].copy()
    y = np.arange(len(view))
    colors = np.where(view["fresh_300s"].astype(int).eq(1), "#2E7D32", "#C62828")
    ax.barh(y, view["rows"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(view["snapshot_component"])
    ax.set_xlabel("rows")
    ax.set_title("Persisted Stage174 snapshot inventory")
    for idx, row in view.iterrows():
        age_text = "fresh" if int(row["fresh_300s"]) else "stale"
        ax.text(row["rows"] + max(view["rows"].max(), 1) * 0.01, list(view.index).index(idx), f"{int(row['rows'])} {age_text}", va="center", fontsize=8)

    ax = axes[0, 1]
    cov_counts = pd.DataFrame(
        [
            {"field": "contract", "covered": int(coverage["contract_in_snapshot"].sum()), "total": len(coverage)},
            {"field": "position_symbol", "covered": int(coverage["position_symbol_in_snapshot"].sum()), "total": len(coverage)},
            {"field": "tick", "covered": int(coverage["tick_in_snapshot"].sum()), "total": len(coverage)},
        ]
    )
    y = np.arange(len(cov_counts))
    ax.barh(y, cov_counts["total"], color="#E0E0E0", label="required")
    ax.barh(y, cov_counts["covered"], color="#1565C0", label="covered")
    ax.set_yticks(y)
    ax.set_yticklabels(cov_counts["field"])
    ax.set_xlabel("Stage591 rows")
    ax.set_title("Stage591 symbol coverage in persisted snapshot")
    for idx, row in cov_counts.iterrows():
        ax.text(row["total"] + 0.05, idx, f"{int(row['covered'])}/{int(row['total'])}", va="center", fontsize=8)
    ax.legend(loc="lower right")

    ax = axes[1, 0]
    symbols = readiness["vt_symbol"].astype(str) + "\n" + readiness["watch_priority"].astype(str).str.slice(0, 18)
    matrix = (
        heatmap.pivot_table(index="bridge_signal_id", columns="field", values="passed", aggfunc="max")
        .reindex(readiness["bridge_signal_id"])
        .reindex(columns=PRE_SUBMIT_HEATMAP_FIELDS)
        .fillna(0)
        .astype(float)
    )
    ax.imshow(matrix.values, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#C62828", "#2E7D32"]), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(PRE_SUBMIT_HEATMAP_FIELDS)))
    ax.set_xticklabels(["ref", "payload", "contract", "account", "position", "limit", "band", "margin", "operator"], rotation=30, ha="right")
    ax.set_yticks(np.arange(len(symbols)))
    ax.set_yticklabels(symbols, fontsize=8)
    ax.set_title("Validator readiness after loading persisted snapshot")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, "Y" if matrix.iloc[i, j] else "N", ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    ax = axes[1, 1]
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    y = np.arange(len(failed))
    ax.barh(y, np.ones(len(failed)), color="#C62828")
    ax.set_yticks(y)
    ax.set_yticklabels(failed["gate"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Failed hard gates")
    for idx, row in failed.reset_index(drop=True).iterrows():
        ax.text(0.02, idx, f"FAIL {row['observed']}", ha="left", va="center", color="white", fontsize=8, fontweight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    inventory: pd.DataFrame,
    coverage: pd.DataFrame,
    readiness: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    lines = [
        "# Stage607 Read-Only Snapshot Bridge Audit",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- checked_at: `{decision['checked_at']}`",
        "- stage nature: file-only read-only snapshot bridge audit; no CTP refresh, no broker order.",
        f"- decision: `{decision['decision']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`",
        "",
        "## External Research And Judgment",
        "",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "Judgment: existing persisted Stage174 snapshots can be loaded into the Stage606 validator, but they must still satisfy freshness, symbol coverage, tick availability, position state and operator gates. Historical Stage591 rows use 2025 contracts, so a 2026 read-only snapshot cannot prove live context for them.",
        "",
        "## Key Metrics",
        "",
        f"- stage174_status: `{decision['stage174_status']}`",
        f"- snapshot_generated_at: `{decision['snapshot_generated_at']}`",
        f"- snapshot_age_seconds: `{decision['snapshot_age_seconds']}`",
        f"- snapshot rows: contracts `{decision['contract_rows']}`, accounts `{decision['account_rows']}`, positions `{decision['position_rows']}`, ticks `{decision['tick_rows']}`",
        f"- Stage591 contract coverage: `{decision['stage591_contract_coverage']}/{decision['submit_plan_rows']}`",
        f"- Stage591 tick coverage: `{decision['stage591_tick_coverage']}/{decision['submit_plan_rows']}`",
        f"- live_context_present_rows: `{decision['live_context_present_rows']}/{decision['context_rows_required']}`",
        f"- real_submit_allowed_rows: `{decision['real_submit_allowed_rows']}/{decision['submit_plan_rows']}`",
        f"- hard_gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Failed Gates",
        "",
        _md_table(failed, ["gate", "observed", "required", "rationale"], max_rows=20),
        "",
        "## Snapshot Inventory",
        "",
        _md_table(inventory, ["snapshot_component", "rows", "generated_at", "age_seconds", "fresh_300s", "source_status"], max_rows=20),
        "",
        "## Symbol Coverage",
        "",
        _md_table(coverage, ["vt_symbol", "watch_priority", "contract_in_snapshot", "position_symbol_in_snapshot", "tick_in_snapshot", "snapshot_coverage_status"], max_rows=10),
        "",
        "## Order Readiness",
        "",
        _md_table(readiness, ["vt_symbol", "watch_priority", "live_context_passed_fields", "live_context_total_fields", "real_submit_allowed", "next_blocker_class"], max_rows=10),
        "",
        "## Visual Review Notes",
        "",
        "- The upper-left panel shows contracts/accounts/positions files exist, but the red stale color is the key point.",
        "- The upper-right panel shows Stage591 historical symbols are not covered by the persisted snapshot; this is expected because those are old 2025 contracts.",
        "- The lower-left heatmap should stay green only for ref/payload and red for live fields.",
        "- The lower-right failed gates make the next step precise: current read-only snapshot must be refreshed for current tradable symbols, and tick rows must be captured.",
        "",
        "## Conclusion",
        "",
        "Stage607 successfully loads the persisted read-only snapshot into the validator, but it does not improve real-submit readiness. The snapshot is stale, has no tick rows, and does not cover the historical Stage591 symbols. This proves the bridge works as a file interface, while also proving that old snapshots cannot close the no-bias execution claim.",
        "",
        "## Overfitting Reflection",
        "",
        "No. This is an execution-evidence audit with no strategy, selector, product, or return changes.",
        "",
        "## Continue Value Reflection",
        "",
        "Yes. It exposes a concrete next step: refresh read-only snapshots for current/future submit-plan symbols and include tick capture before any exact vt_orderid writer is attempted.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    submit_plan = _read_csv(STAGE591_SUBMIT_PLAN)
    summary = _read_json(STAGE174_SUMMARY)
    snapshots = load_stage174_readonly_snapshot(summary)

    context, readiness = evaluate_submit_plan_live_context(
        submit_plan,
        snapshots=snapshots,
        now=now,
        operator_confirmed=False,
        allow_historical_reference_price=False,
    )
    heatmap = build_pre_submit_heatmap_rows(readiness, context)
    inventory = build_snapshot_inventory(summary, snapshots, now)
    coverage = build_symbol_coverage(submit_plan, snapshots)
    gates = build_gates(summary, inventory, coverage, context, readiness)

    age = _age_seconds(summary.get("generated_at"), now)
    hard_total = int(len(gates[gates["severity"].eq("hard")]))
    hard_passed = int(gates.loc[gates["severity"].eq("hard"), "passed"].sum())
    decision = {
        "decision": "persisted_readonly_snapshot_bridge_loads_but_stale_no_tick_no_symbol_coverage",
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "stage174_status": _clean(summary.get("status")),
        "snapshot_generated_at": _clean(summary.get("generated_at")),
        "snapshot_age_seconds": age,
        "submit_plan_rows": int(len(submit_plan)),
        "contract_rows": int(len(snapshots.get("contracts", []))),
        "account_rows": int(len(snapshots.get("accounts", []))),
        "position_rows": int(len(snapshots.get("positions", []))),
        "tick_rows": int(len(snapshots.get("ticks", []))),
        "stage591_contract_coverage": int(coverage["contract_in_snapshot"].sum()),
        "stage591_tick_coverage": int(coverage["tick_in_snapshot"].sum()),
        "context_rows_required": int(len(context)),
        "live_context_present_rows": int(context["present_in_adapter"].sum()),
        "real_submit_allowed_rows": int(readiness["real_submit_allowed"].sum()),
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "send_order_api_called_count": 0,
        "ctp_connection_attempted": False,
        "next_required_step": "refresh_readonly_snapshot_for_current_submit_plan_with_ticks",
        "overfit_reflection": "No. File snapshot bridge audit only; no strategy/return changes.",
        "continue_value_reflection": "Yes. It proves loader works and clarifies why old snapshots cannot close live context.",
    }

    inventory.to_csv(SNAPSHOT_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(SYMBOL_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    context.to_csv(CONTEXT_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    heatmap.to_csv(HEATMAP_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    plot_chart(inventory, coverage, heatmap, readiness, gates)
    write_report(inventory, coverage, readiness, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
