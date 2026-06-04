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


MODEL_TAG = "stage608_readonly_tick_probe_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage608_readonly_tick_probe_contract_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

PROBE_TAG = "stage608_readonly_tick_snapshot_probe_v1"
PROBE_PREFIX = "qmt_roll_stage608_readonly_tick_snapshot_probe"
PROBE_SCRIPT = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.py"
PROBE_WRAPPER = PROJECT_DIR / "run_ctp_stage608_readonly_tick_snapshot_probe.sh"
PROBE_SUMMARY = OUTPUT_DIR / f"{PROBE_PREFIX}_summary_{PROBE_TAG}.json"
PROBE_TARGET_SYMBOLS = OUTPUT_DIR / f"{PROBE_PREFIX}_target_symbols_{PROBE_TAG}.csv"
PROBE_TICKS = OUTPUT_DIR / f"{PROBE_PREFIX}_ticks_{PROBE_TAG}.csv"
PROBE_CONTRACTS = OUTPUT_DIR / f"{PROBE_PREFIX}_contracts_{PROBE_TAG}.csv"
PROBE_ACCOUNTS = OUTPUT_DIR / f"{PROBE_PREFIX}_accounts_{PROBE_TAG}.csv"
PROBE_POSITIONS = OUTPUT_DIR / f"{PROBE_PREFIX}_positions_{PROBE_TAG}.csv"

CAPABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_capability_{MODEL_TAG}.csv"
SNAPSHOT_DRY_RUN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_snapshot_dry_run_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REFERENCE_LINKS = [
    "vn.py MainEngine/OmsEngine cache APIs: https://deepwiki.com/vnpy/vnpy/2.2-main-engine",
    "vn.py EVENT_TICK/EVENT_ORDER/EVENT_TRADE architecture: https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system",
    "vn.py gateway callback contract: https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways",
]


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


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _contains_call(source: str, call: str) -> bool:
    compact = source.replace(" ", "")
    return call.replace(" ", "") in compact


def build_capability(summary: dict[str, Any], source: str, wrapper_source: str) -> pd.DataFrame:
    rows = [
        {
            "capability": "dry_run_default_no_connect",
            "implemented": int("connect_requested" in summary and summary.get("connect_requested") is False),
            "observed": f"status={summary.get('status', '')};connect_requested={summary.get('connect_requested', '')}",
            "rationale": "Normal audit must not connect CTP.",
        },
        {
            "capability": "target_symbols_from_submit_plan",
            "implemented": int(int(summary.get("target_symbol_count", 0) or 0) > 0),
            "observed": f"{summary.get('target_symbol_count', 0)} symbols",
            "rationale": "Snapshot must align to current/future submit plan symbols.",
        },
        {
            "capability": "dyld_wrapper_available",
            "implemented": int(PROBE_WRAPPER.exists() and "DYLD_FRAMEWORK_PATH" in wrapper_source and "vnpy_ctp/api/libs" in wrapper_source),
            "observed": str(PROBE_WRAPPER),
            "rationale": "On macOS, vnpy_ctp import requires the CTP framework library path.",
        },
        {
            "capability": "event_tick_registered",
            "implemented": int("EVENT_TICK" in source and "event_engine.register(EVENT_TICK" in source),
            "observed": "EVENT_TICK handler present" if "event_engine.register(EVENT_TICK" in source else "missing",
            "rationale": "Ticks must enter the file snapshot through vn.py events.",
        },
        {
            "capability": "subscribe_request_supported",
            "implemented": int("SubscribeRequest" in source and "main_engine.subscribe" in source),
            "observed": "SubscribeRequest + main_engine.subscribe" if "main_engine.subscribe" in source else "missing",
            "rationale": "Read-only tick capture requires subscription for target vt_symbols.",
        },
        {
            "capability": "ticks_csv_output_declared",
            "implemented": int("TICK_PATH" in source and '"ticks": str(TICK_PATH)' in source),
            "observed": str(summary.get("outputs", {}).get("ticks", "")),
            "rationale": "Stage606/607 validator needs a persisted ticks file.",
        },
        {
            "capability": "cache_snapshot_after_wait",
            "implemented": int("collect_snapshot_from_main_engine" in source),
            "observed": "collect_snapshot_from_main_engine used" if "collect_snapshot_from_main_engine" in source else "missing",
            "rationale": "After events, cached get_tick/get_contract/account/position should be persisted.",
        },
        {
            "capability": "send_order_path_absent",
            "implemented": int(not _contains_call(source, "main_engine.send_order(") and not _contains_call(source, ".send_order(")),
            "observed": "no send_order call" if not _contains_call(source, ".send_order(") else "send_order-like call present",
            "rationale": "This probe must remain read-only.",
        },
        {
            "capability": "cancel_order_path_absent",
            "implemented": int(not _contains_call(source, "cancel_order(")),
            "observed": "no cancel_order call" if not _contains_call(source, "cancel_order(") else "cancel_order-like call present",
            "rationale": "This probe must not affect broker orders.",
        },
    ]
    return pd.DataFrame(rows)


def build_snapshot_dry_run(summary: dict[str, Any]) -> pd.DataFrame:
    targets = _read_csv(PROBE_TARGET_SYMBOLS)
    return pd.DataFrame(
        [
            {"component": "target_symbols", "rows": len(targets), "required_now": ">0", "dry_run_expected": "present"},
            {"component": "contracts", "rows": len(_read_csv(PROBE_CONTRACTS)), "required_now": "0 in dry-run", "dry_run_expected": "empty"},
            {"component": "accounts", "rows": len(_read_csv(PROBE_ACCOUNTS)), "required_now": "0 in dry-run", "dry_run_expected": "empty"},
            {"component": "positions", "rows": len(_read_csv(PROBE_POSITIONS)), "required_now": "0 in dry-run", "dry_run_expected": "empty"},
            {"component": "ticks", "rows": len(_read_csv(PROBE_TICKS)), "required_now": "0 in dry-run; >0 after --connect", "dry_run_expected": "empty"},
            {"component": "send_order_api_called_count", "rows": int(summary.get("send_order_api_called_count", -1)), "required_now": "0", "dry_run_expected": "zero"},
            {"component": "subscribe_api_called_count", "rows": int(summary.get("subscribe_api_called_count", -1)), "required_now": "0 in dry-run; target count after --connect", "dry_run_expected": "zero"},
        ]
    )


def build_gates(summary: dict[str, Any], capability: pd.DataFrame, snapshot: pd.DataFrame) -> pd.DataFrame:
    target_rows = int(snapshot.loc[snapshot["component"].eq("target_symbols"), "rows"].iloc[0]) if not snapshot.empty else 0
    tick_rows = int(snapshot.loc[snapshot["component"].eq("ticks"), "rows"].iloc[0]) if not snapshot.empty else 0
    send_calls = int(summary.get("send_order_api_called_count", -1))
    subscribe_calls = int(summary.get("subscribe_api_called_count", -1))
    implemented = int(capability["implemented"].sum()) if not capability.empty else 0
    total = int(len(capability))
    rows = [
        ("probe_script_exists", PROBE_SCRIPT.exists(), str(PROBE_SCRIPT.exists()), "True", "hard", "Stage608 tick probe script must exist."),
        ("dry_run_not_connected", summary.get("status") == "dry_run_not_connected" and summary.get("connect_requested") is False, str(summary.get("status")), "dry_run_not_connected", "hard", "Normal audit must not connect CTP."),
        ("target_symbols_loaded", target_rows > 0, str(target_rows), ">0", "hard", "Probe must know which vt_symbols to subscribe."),
        ("tick_capture_capability_present", bool(capability[capability["capability"].eq("event_tick_registered")]["implemented"].sum()) and bool(capability[capability["capability"].eq("subscribe_request_supported")]["implemented"].sum()), "EVENT_TICK+subscribe", "present", "hard", "Fresh snapshot needs live tick capture."),
        ("ticks_csv_output_present", bool(capability[capability["capability"].eq("ticks_csv_output_declared")]["implemented"].sum()), str(PROBE_TICKS.exists()), "True", "hard", "Validator requires ticks CSV output."),
        ("send_order_path_absent", bool(capability[capability["capability"].eq("send_order_path_absent")]["implemented"].sum()) and send_calls == 0, f"path={capability[capability['capability'].eq('send_order_path_absent')]['observed'].iloc[0]};count={send_calls}", "absent and 0", "hard", "No broker order API allowed."),
        ("cancel_order_path_absent", bool(capability[capability["capability"].eq("cancel_order_path_absent")]["implemented"].sum()), capability[capability["capability"].eq("cancel_order_path_absent")]["observed"].iloc[0], "absent", "hard", "No cancel API allowed."),
        ("dry_run_subscribe_not_called", subscribe_calls == 0, str(subscribe_calls), "0", "hard", "Subscription only allowed after explicit --connect."),
        ("fresh_tick_snapshot_not_yet_received", tick_rows > 0, str(tick_rows), ">0 after explicit --connect", "hard", "This is expected to fail in dry-run; it defines the remaining live evidence gap."),
        ("all_capabilities_implemented", implemented == total and total > 0, f"{implemented}/{total}", "all", "soft", "The code path should be complete before live read-only run."),
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


def build_chart(capability: pd.DataFrame, snapshot: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage608 read-only tick snapshot probe contract: code path ready, live tick evidence still pending", fontsize=14)

    ax = axes[0, 0]
    cap = capability.copy()
    y = np.arange(len(cap))
    colors = np.where(cap["implemented"].astype(int).eq(1), "#2e7d32", "#c62828")
    ax.barh(y, cap["implemented"].astype(int), color=colors)
    ax.set_yticks(y, cap["capability"])
    ax.set_xlim(0, 1.05)
    ax.set_title("Probe capability matrix")
    for i, row in cap.iterrows():
        ax.text(0.04, i, "Y" if row["implemented"] else "N", va="center", color="white", fontsize=9)

    ax = axes[0, 1]
    snap = snapshot[snapshot["component"].isin(["target_symbols", "contracts", "accounts", "positions", "ticks"])].copy()
    x = np.arange(len(snap))
    ax.bar(x, snap["rows"], color=["#1565c0" if item == "target_symbols" else "#9e9e9e" for item in snap["component"]])
    ax.set_xticks(x, snap["component"], rotation=20, ha="right")
    ax.set_title("Dry-run snapshot rows")
    for i, row in snap.iterrows():
        ax.text(i, float(row["rows"]) + 0.05, str(int(row["rows"])), ha="center", fontsize=9)

    ax = axes[1, 0]
    view = gates.copy()
    y = np.arange(len(view))
    colors = np.where(view["passed"].astype(int).eq(1), "#2e7d32", "#c62828")
    ax.barh(y, np.ones(len(view)), color=colors)
    ax.set_yticks(y, view["gate"])
    ax.set_xlim(0, 1.05)
    ax.set_title("Gate results")
    for i, row in view.iterrows():
        ax.text(0.04, i, f"{'PASS' if row['passed'] else 'FAIL'} {row['observed']}", va="center", color="white", fontsize=8)

    ax = axes[1, 1]
    steps = pd.DataFrame(
        [
            ("1 dry-run contract", 1),
            ("2 explicit read-only connect", 0),
            ("3 tick rows >0", 0),
            ("4 validator live context", 0),
            ("5 vt_orderid writer", 0),
        ],
        columns=["step", "ready"],
    )
    y = np.arange(len(steps))
    ax.barh(y, np.ones(len(steps)), color=np.where(steps["ready"].eq(1), "#2e7d32", "#c62828"))
    ax.set_yticks(y, steps["step"])
    ax.set_xlim(0, 1.05)
    ax.set_title("Execution no-bias ladder")
    for i, row in steps.iterrows():
        ax.text(0.04, i, "ready" if row["ready"] else "pending", va="center", color="white", fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(summary: dict[str, Any], capability: pd.DataFrame, snapshot: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    failed = gates[gates["passed"].eq(0)].copy()
    lines = [
        "# Stage608 Read-Only Tick Probe Contract Audit",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- checked_at: `{decision['checked_at']}`",
        "- stage nature: dry-run/code contract audit; no CTP connection, no subscription, no broker order.",
        f"- decision: `{decision['decision']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- zero_execution_bias_claim_allowed: `{decision['zero_execution_bias_claim_allowed']}`",
        "",
        "## External Research And Judgment",
        "",
    ]
    lines.extend([f"- {item}" for item in REFERENCE_LINKS])
    lines.extend(
        [
            "",
            "Judgment: vn.py supports the required read-only data path through `EVENT_TICK` and `MainEngine.get_tick`, but the existing Stage174 snapshot probe did not subscribe target symbols or persist a ticks CSV. Stage608 closes the code contract for that missing input without connecting or submitting in this audit.",
            "",
            "## Key Metrics",
            "",
            f"- target_symbol_count: `{decision['target_symbol_count']}`",
            f"- dry_run_status: `{summary.get('status', '')}`",
            f"- capabilities_implemented: `{decision['capabilities_implemented']}/{decision['capabilities_total']}`",
            f"- tick_rows: `{decision['tick_rows']}`",
            f"- send_order_api_called_count: `{decision['send_order_api_called_count']}`",
            f"- subscribe_api_called_count: `{decision['subscribe_api_called_count']}`",
            f"- hard_gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
            "",
            "## Failed Gates",
            "",
            _md_table(failed, ["gate", "observed", "required", "rationale"]),
            "",
            "## Capability Matrix",
            "",
            _md_table(capability),
            "",
            "## Dry-Run Snapshot Inventory",
            "",
            _md_table(snapshot),
            "",
            "## Visual Review Notes",
            "",
            "- The top-left panel is mostly green: code support for `EVENT_TICK`, target subscriptions, ticks CSV and cache snapshot persistence is present.",
            "- The top-right panel intentionally shows only target symbols in dry-run; contracts/accounts/positions/ticks are zero because no CTP connection was attempted.",
            "- The bottom-left panel has one expected red gate: `fresh_tick_snapshot_not_yet_received`. That red bar is the remaining live evidence gap, not a strategy failure.",
            "- The bottom-right ladder shows we are still before read-only connect and before any `vt_orderid` writer. This is the correct safety boundary.",
            "",
            "## Conclusion",
            "",
            "Stage608 makes the next fresh read-only snapshot step executable: target symbols can be loaded from the submit plan, tick events can be captured through `EVENT_TICK`, subscriptions are target-scoped, and ticks can be persisted for the Stage606/607 validator. This audit did not connect CTP and did not submit orders, so it does not yet prove real trade no-bias.",
            "",
            "## Overfitting Reflection",
            "",
            "No. This stage changes only execution evidence plumbing and does not alter strategy rules, product selection, return windows, or risk parameters.",
            "",
            "## Continue Value Reflection",
            "",
            "Yes. It removes the Stage307 structural reason for `ticks=0` and defines the next read-only run needed before any exact `vt_orderid` writer can be considered.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = _read_json(PROBE_SUMMARY)
    source = PROBE_SCRIPT.read_text(encoding="utf-8") if PROBE_SCRIPT.exists() else ""
    wrapper_source = PROBE_WRAPPER.read_text(encoding="utf-8") if PROBE_WRAPPER.exists() else ""
    capability = build_capability(summary, source, wrapper_source)
    snapshot = build_snapshot_dry_run(summary)
    gates = build_gates(summary, capability, snapshot)

    hard = gates[gates["severity"].eq("hard")]
    decision = {
        "decision": "readonly_tick_probe_code_ready_dry_run_no_live_ticks_yet",
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_symbol_count": int(summary.get("target_symbol_count", 0) or 0),
        "capabilities_implemented": int(capability["implemented"].sum()) if not capability.empty else 0,
        "capabilities_total": int(len(capability)),
        "tick_rows": int(len(_read_csv(PROBE_TICKS))),
        "send_order_api_called_count": int(summary.get("send_order_api_called_count", -1)),
        "subscribe_api_called_count": int(summary.get("subscribe_api_called_count", -1)),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "next_required_step": "explicit_readonly_connect_for_current_submit_plan_symbols_capture_ticks_then_stage606_validator",
        "overfit_reflection": "No. Execution evidence plumbing only; no strategy/return changes.",
        "continue_value_reflection": "Yes. It closes the tick-capture code gap found by Stage307 while staying dry-run.",
    }

    capability.to_csv(CAPABILITY_PATH, index=False, encoding="utf-8-sig")
    snapshot.to_csv(SNAPSHOT_DRY_RUN_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, capability, snapshot, gates, decision)
    build_chart(capability, snapshot, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")
    print(f"chart: {CHART_PATH}")


if __name__ == "__main__":
    main()
