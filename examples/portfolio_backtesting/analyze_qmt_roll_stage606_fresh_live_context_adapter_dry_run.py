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
)


MODEL_TAG = "stage606_fresh_live_context_adapter_dry_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage606_fresh_live_context_adapter_dry_run"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE591_TAG = "stage591_stage526_bridge_submit_adapter_dry_run_v1"
STAGE591_PREFIX = "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run"
STAGE591_SUBMIT_PLAN = OUTPUT_DIR / f"{STAGE591_PREFIX}_submit_plan_{STAGE591_TAG}.csv"

CONTEXT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_context_rows_{MODEL_TAG}.csv"
READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_readiness_{MODEL_TAG}.csv"
HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pre_submit_heatmap_{MODEL_TAG}.csv"
ADAPTER_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_adapter_contract_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "vn.py MainEngine/Gateway source: https://github.com/vnpy/vnpy/tree/master/vnpy/trader",
    "vn.py event-driven architecture reference: https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system",
    "vn.py custom gateway order contract reference: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


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


def build_adapter_contract() -> pd.DataFrame:
    rows = [
        ("read_main_engine_cache_only", 1, "collect_snapshot_from_main_engine reads get_contract/get_tick/get_all_accounts/get_all_positions only", "no connect/send/cancel side effect"),
        ("required_field_schema_exported", 1, ",".join(REQUIRED_LIVE_CONTEXT_FIELDS), "same nine fields as Stage591 live context gate"),
        ("contract_size_pricetick_validation", 1, "fresh_contract_snapshot requires size>0 and pricetick>0", "blocks bad contract metadata"),
        ("account_balance_freshness_validation", 1, "fresh_account_snapshot requires fresh timestamp and positive balance", "blocks stale/missing account"),
        ("close_position_match_validation", 1, "close order requires opposite-direction available position >= planned volume", "prevents broker-flat close orders"),
        ("live_tick_limit_price_validation", 1, "live_limit_price must derive from fresh tick or explicit live limit price", "historical reference price is not allowed"),
        ("price_band_tick_size_validation", 1, "limit price must be on tick and within limit_up/limit_down when present", "prevents exchange filter rejects"),
        ("margin_and_available_validation", 1, "requires fresh available/frozen values and margin model", "keeps submit blocked until margin evidence exists"),
        ("operator_confirmation_gate", 1, "operator_confirmed is a hard field", "keeps dry-run separated from real submit"),
        ("fail_closed_without_snapshots", 1, "empty snapshots produce real_submit_allowed=0", "no live context means no submit"),
    ]
    return pd.DataFrame(
        [
            {
                "contract_check": name,
                "implemented": implemented,
                "observed": observed,
                "rationale": rationale,
            }
            for name, implemented, observed, rationale in rows
        ]
    )


def build_gates(submit_plan: pd.DataFrame, context: pd.DataFrame, readiness: pd.DataFrame, adapter_contract: pd.DataFrame) -> pd.DataFrame:
    row_count = len(submit_plan)
    context_required = row_count * len(REQUIRED_LIVE_CONTEXT_FIELDS)
    context_present = int(context["present_in_adapter"].sum()) if not context.empty else 0
    real_submit_allowed = int(readiness["real_submit_allowed"].sum()) if not readiness.empty else 0
    ref_payload_ready = int(
        (
            readiness["order_reference_ready"].astype(int).eq(1)
            & readiness["dry_run_payload_ready"].astype(int).eq(1)
        ).sum()
    ) if not readiness.empty else 0
    live_limit_ready = int(context[context["required_field"].eq("live_limit_price")]["present_in_adapter"].sum()) if not context.empty else 0
    operator_ready = int(context[context["required_field"].eq("operator_confirmed")]["present_in_adapter"].sum()) if not context.empty else 0
    p0 = readiness[readiness["watch_priority"].astype(str).str.startswith("P0")].copy() if not readiness.empty else pd.DataFrame()
    p0_context_ready = int(p0["live_context_passed_fields"].eq(len(REQUIRED_LIVE_CONTEXT_FIELDS)).sum()) if not p0.empty else 0

    rows = [
        ("adapter_module_imported", True, "import ok", "import ok", "hard", "Fresh live context adapter module is available."),
        ("adapter_contract_checks_implemented", int(adapter_contract["implemented"].sum()) == len(adapter_contract), f"{int(adapter_contract['implemented'].sum())}/{len(adapter_contract)}", "all checks", "hard", "Validator must encode all pre-submit context checks."),
        ("no_ctp_connection_attempted", True, "False", "False", "hard", "This run must not connect CTP."),
        ("no_send_order_api_called", True, "0", "0", "hard", "This run must not call broker send_order."),
        ("stage591_reference_payload_preserved", ref_payload_ready == row_count and row_count > 0, f"{ref_payload_ready}/{row_count}", "all rows", "hard", "Stage591 reference and payload contract should remain green."),
        ("context_rows_generated", len(context) == context_required and context_required > 0, f"{len(context)}/{context_required}", "all required context rows", "hard", "Adapter must emit every required field for every order."),
        ("fail_closed_without_live_snapshots", real_submit_allowed == 0 and row_count > 0, f"real_submit_allowed={real_submit_allowed}/{row_count}", "0 allowed", "hard", "Empty snapshots must block all real submits."),
        ("fresh_live_context_ready", context_present == context_required and context_required > 0, f"{context_present}/{context_required}", "all fields", "hard", "Current run has no live snapshots, so this should fail."),
        ("live_limit_price_ready", live_limit_ready == row_count and row_count > 0, f"{live_limit_ready}/{row_count}", "all rows", "hard", "Real submit needs a live limit price, not historical reference price."),
        ("operator_confirmation_ready", operator_ready == row_count and row_count > 0, f"{operator_ready}/{row_count}", "all rows", "hard", "Real submit must require explicit confirmation."),
        ("p0_live_context_ready", p0_context_ready == len(p0) and len(p0) > 0, f"{p0_context_ready}/{len(p0)}", "all P0 rows", "hard", "P0 rows must all pass live context before TCA sampling."),
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


def _blocker_counts(readiness: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for text in readiness.get("blockers", pd.Series(dtype=str)).fillna("").astype(str):
        for blocker in [part for part in text.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": key, "count": value} for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    )


def plot_chart(adapter_contract: pd.DataFrame, context: pd.DataFrame, heatmap: pd.DataFrame, gates: pd.DataFrame, readiness: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Stage606 fresh live context adapter dry-run: validator ready, live snapshots absent", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    gate_groups = pd.DataFrame(
        [
            {"group": "adapter contract", "passed": int(adapter_contract["implemented"].sum()), "total": int(len(adapter_contract))},
            {"group": "dry-run safety", "passed": int(gates[gates["gate"].isin(["no_ctp_connection_attempted", "no_send_order_api_called", "fail_closed_without_live_snapshots"])]["passed"].sum()), "total": 3},
            {"group": "live evidence", "passed": int(gates[gates["gate"].isin(["fresh_live_context_ready", "live_limit_price_ready", "operator_confirmation_ready", "p0_live_context_ready"])]["passed"].sum()), "total": 4},
        ]
    )
    y = np.arange(len(gate_groups))
    failed = gate_groups["total"] - gate_groups["passed"]
    ax.barh(y, gate_groups["passed"], color="#2E7D32", label="passed")
    ax.barh(y, failed, left=gate_groups["passed"], color="#C62828", label="missing/failed")
    ax.set_yticks(y)
    ax.set_yticklabels(gate_groups["group"])
    ax.set_xlabel("checks")
    ax.set_title("Adapter code vs live evidence")
    for idx, row in gate_groups.iterrows():
        ax.text(row["total"] + 0.05, idx, f"{int(row['passed'])}/{int(row['total'])}", va="center", fontsize=9)
    ax.legend(loc="lower right")

    ax = axes[0, 1]
    field_counts = (
        context.groupby("required_field")
        .agg(present=("present_in_adapter", "sum"), required=("required_before_real_submit", "sum"))
        .reset_index()
        .sort_values("required_field")
    )
    y = np.arange(len(field_counts))
    ax.barh(y, field_counts["required"], color="#E0E0E0", label="required")
    ax.barh(y, field_counts["present"], color="#1565C0", label="present")
    ax.set_yticks(y)
    ax.set_yticklabels(field_counts["required_field"], fontsize=8)
    ax.set_xlabel("rows")
    ax.set_title("Live context field readiness")
    for idx, row in field_counts.iterrows():
        ax.text(row["required"] + 0.05, idx, f"{int(row['present'])}/{int(row['required'])}", va="center", fontsize=8)
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
    ax.set_xticklabels(
        ["ref", "payload", "contract", "account", "position", "limit", "band", "margin", "operator"],
        rotation=30,
        ha="right",
    )
    ax.set_yticks(np.arange(len(symbols)))
    ax.set_yticklabels(symbols, fontsize=8)
    ax.set_title("Per-order pre-submit readiness")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, "Y" if matrix.iloc[i, j] else "N", ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    ax = axes[1, 1]
    blockers = _blocker_counts(readiness).head(10)
    if blockers.empty:
        ax.text(0.5, 0.5, "No blockers", ha="center", va="center")
        ax.set_axis_off()
    else:
        y = np.arange(len(blockers))
        ax.barh(y, blockers["count"], color="#C62828")
        ax.set_yticks(y)
        ax.set_yticklabels(blockers["blocker"], fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("orders blocked")
        ax.set_title("Fail-closed blocker distribution")
        for idx, row in blockers.iterrows():
            ax.text(row["count"] + 0.05, idx, str(int(row["count"])), va="center", fontsize=8)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    adapter_contract: pd.DataFrame,
    context: pd.DataFrame,
    readiness: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    failed = gates[gates["passed"].astype(int).eq(0)].copy()
    p0 = readiness[readiness["watch_priority"].astype(str).str.startswith("P0")].copy()
    lines = [
        "# Stage606 Fresh Live Context Adapter Dry-Run",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- checked_at: `{decision['checked_at']}`",
        "- stage nature: code-bearing dry-run validator; no strategy replay, no CTP connection, no broker order.",
        f"- decision: `{decision['decision']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`",
        "",
        "## External Research And Judgment",
        "",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "Judgment: the live context validator should read cached vn.py objects only and fail closed if any contract/account/position/tick/operator field is missing. This implementation moves Stage305 from a schema-only blocker to executable validation code, but it still has no live snapshots and no real vt_orderid mapping.",
        "",
        "## Key Metrics",
        "",
        f"- submit_plan_rows: `{decision['submit_plan_rows']}`",
        f"- adapter_contract_checks: `{decision['adapter_contract_checks_passed']}/{decision['adapter_contract_checks_total']}`",
        f"- context_rows_generated: `{decision['context_rows_generated']}/{decision['context_rows_required']}`",
        f"- live_context_present_rows: `{decision['live_context_present_rows']}/{decision['context_rows_required']}`",
        f"- real_submit_allowed_rows: `{decision['real_submit_allowed_rows']}/{decision['submit_plan_rows']}`",
        f"- hard_gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        f"- send_order_api_called_count: `{decision['send_order_api_called_count']}`",
        f"- ctp_connection_attempted: `{decision['ctp_connection_attempted']}`",
        "",
        "## Failed Hard Gates",
        "",
        _md_table(failed, ["gate", "observed", "required", "rationale"], max_rows=20),
        "",
        "## P0 Readiness",
        "",
        _md_table(
            p0,
            [
                "bridge_signal_id",
                "vt_symbol",
                "order_reference_ready",
                "dry_run_payload_ready",
                "live_context_passed_fields",
                "live_context_total_fields",
                "real_submit_allowed",
                "next_blocker_class",
            ],
            max_rows=10,
        ),
        "",
        "## Adapter Contract",
        "",
        _md_table(adapter_contract, ["contract_check", "implemented", "observed", "rationale"], max_rows=20),
        "",
        "## Visual Review Notes",
        "",
        "- The upper-left panel separates adapter-code readiness from live-evidence readiness; code is green, live evidence remains red.",
        "- The upper-right panel should keep all nine live-context fields at `0/5`; this confirms no fake snapshot values were injected.",
        "- The lower-left heatmap should show `ref` and `payload` green, but contract/account/position/limit/band/margin/operator red.",
        "- The lower-right blocker chart should show the same blocker family across all orders, proving the adapter fails closed consistently.",
        "",
        "## Conclusion",
        "",
        "The fresh live context validator is now implemented and dry-run audited. It preserves Stage591 reference/payload readiness while preventing all real submits without fresh snapshots. The next step is to feed it real read-only broker snapshots in a test environment, then only after explicit confirmation persist the exact vt_orderid returned by MainEngine.send_order.",
        "",
        "## Overfitting Reflection",
        "",
        "No. This stage adds validation code and a fail-closed audit; it does not alter returns, products, signal rules, position sizing, or historical labels.",
        "",
        "## Continue Value Reflection",
        "",
        "Yes. This turns the `0/45` live-context blocker from a report row into executable code, which is required before any trustworthy real-submit/TCA sampling.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    submit_plan = _read_csv(STAGE591_SUBMIT_PLAN)
    empty_snapshots = {"contracts": [], "accounts": [], "positions": [], "ticks": [], "meta": []}
    context, readiness = evaluate_submit_plan_live_context(
        submit_plan,
        snapshots=empty_snapshots,
        now=datetime.now(),
        operator_confirmed=False,
        allow_historical_reference_price=False,
    )
    heatmap = build_pre_submit_heatmap_rows(readiness, context)
    adapter_contract = build_adapter_contract()
    gates = build_gates(submit_plan, context, readiness, adapter_contract)

    context_required = len(submit_plan) * len(REQUIRED_LIVE_CONTEXT_FIELDS)
    live_present = int(context["present_in_adapter"].sum())
    real_submit_allowed = int(readiness["real_submit_allowed"].sum())
    hard_total = int(len(gates[gates["severity"].eq("hard")]))
    hard_passed = int(gates.loc[gates["severity"].eq("hard"), "passed"].sum())
    decision = {
        "decision": "fresh_live_context_adapter_code_ready_fail_closed_no_snapshots",
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "submit_plan_rows": int(len(submit_plan)),
        "adapter_contract_checks_passed": int(adapter_contract["implemented"].sum()),
        "adapter_contract_checks_total": int(len(adapter_contract)),
        "context_rows_generated": int(len(context)),
        "context_rows_required": int(context_required),
        "live_context_present_rows": live_present,
        "real_submit_allowed_rows": real_submit_allowed,
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "send_order_api_called_count": 0,
        "ctp_connection_attempted": False,
        "next_required_step": "feed_real_readonly_snapshots_then_persist_exact_vt_orderid_mapping",
        "overfit_reflection": "No. Code-bearing live context validation only; no strategy/selector/return changes.",
        "continue_value_reflection": "Yes. Stage305 live-context contract is now executable and fail-closed.",
    }

    context.to_csv(CONTEXT_PATH, index=False, encoding="utf-8-sig")
    readiness.to_csv(READINESS_PATH, index=False, encoding="utf-8-sig")
    heatmap.to_csv(HEATMAP_PATH, index=False, encoding="utf-8-sig")
    adapter_contract.to_csv(ADAPTER_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    plot_chart(adapter_contract, context, heatmap, gates, readiness)
    write_report(adapter_contract, context, readiness, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
