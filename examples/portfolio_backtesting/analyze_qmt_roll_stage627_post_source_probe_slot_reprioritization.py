from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage627_post_source_probe_slot_reprioritization_v1"
OUTPUT_PREFIX = "qmt_roll_stage627_post_source_probe_slot_reprioritization"

STAGE604_ANNUAL_CAPTURE = OUTPUT_DIR / (
    "qmt_roll_stage604_low_single_risk_slot_allocator_audit_annual_capture_"
    "stage604_low_single_risk_slot_allocator_audit_v1.csv"
)
STAGE604_HOLDING_BOUNDARY = OUTPUT_DIR / (
    "qmt_roll_stage604_low_single_risk_slot_allocator_audit_holding_boundary_"
    "stage604_low_single_risk_slot_allocator_audit_v1.csv"
)
STAGE621_FAMILY_PRIORITY = OUTPUT_DIR / (
    "qmt_roll_stage621_risk_slot_gap_priority_board_family_priority_"
    "stage621_risk_slot_gap_priority_board_v1.csv"
)
STAGE621_SLOT_LADDER = OUTPUT_DIR / (
    "qmt_roll_stage621_risk_slot_gap_priority_board_slot_ladder_"
    "stage621_risk_slot_gap_priority_board_v1.csv"
)
STAGE625_RAW_LEDGER = OUTPUT_DIR / (
    "qmt_roll_stage625_public_source_raw_text_probe_raw_fetch_ledger_"
    "stage625_public_source_raw_text_probe_v1.csv"
)
STAGE625_PRODUCT_SUMMARY = OUTPUT_DIR / (
    "qmt_roll_stage625_public_source_raw_text_probe_product_summary_"
    "stage625_public_source_raw_text_probe_v1.csv"
)
STAGE626_PROBE_LEDGER = OUTPUT_DIR / (
    "qmt_roll_stage626_czce_412_route_forensic_probe_ledger_"
    "stage626_czce_412_route_forensic_v1.csv"
)

FAMILY_REPRIORITIZATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_reprioritization_{MODEL_TAG}.csv"
SOURCE_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_delta_{MODEL_TAG}.csv"
SCENARIO_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slot_scenarios_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_EFFECTIVE_SLOTS = 7
CURRENT_EFFECTIVE_SLOTS = 4
SLOTS_IF_BLACK_CLOSED = 5
PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0
MAX_CORE_CORR_OBSERVE = 0.10

REFERENCE_LINKS = [
    "AIMA Managed futures and varying correlations: https://www.aima.org/article/managed-futures-and-varying-correlations.html",
    "Man Group trend following market mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "SSRN Trend Following, Risk Parity and Momentum in Commodity Futures: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813",
    "GitHub risk-parity topic / Riskfolio-Lib / skfolio: https://github.com/topics/risk-parity",
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


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


def _split_csv_cell(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _slot_risk(slots: int) -> float:
    return 100.0 / slots if slots else np.nan


def build_source_delta(stage625_product: pd.DataFrame, stage625_raw: pd.DataFrame, stage626_probe: pd.DataFrame) -> pd.DataFrame:
    product_rows: list[dict[str, Any]] = []
    raw = stage625_raw.copy()
    product_summary = stage625_product.copy()
    probe = stage626_probe.copy()

    for column in [
        "fetched_ok_rows",
        "event_auto_monitor_rows",
        "history_selector_rows",
        "event_signal_ready_rows",
        "total_bytes",
        "pit_received_dates",
    ]:
        product_summary[column] = _num(product_summary, column)
    for column in ["route_ready", "http_412", "http_404", "usable_for_forward_monitor"]:
        probe[column] = _num(probe, column)
    probe["_product_tokens"] = probe["product_vt_symbol"].map(_split_csv_cell)
    expanded_probe_rows: list[dict[str, Any]] = []
    for _, probe_row in probe.iterrows():
        tokens = probe_row["_product_tokens"] or [str(probe_row["product_vt_symbol"])]
        weight = 1.0 / len(tokens)
        for token in tokens:
            expanded_probe_rows.append(
                {
                    "product_vt_symbol": token,
                    "weighted_probe_rows": weight,
                    "weighted_route_ready_rows": float(probe_row["route_ready"]) * weight,
                    "weighted_http_412_rows": float(probe_row["http_412"]) * weight,
                    "weighted_http_404_rows": float(probe_row["http_404"]) * weight,
                }
            )
    expanded_probe = pd.DataFrame(expanded_probe_rows)

    for _, row in product_summary.iterrows():
        product = str(row["product_vt_symbol"])
        product_probe = expanded_probe[expanded_probe["product_vt_symbol"].astype(str).eq(product)] if not expanded_probe.empty else pd.DataFrame()
        product_rows.append(
            {
                "product_family": str(row["product_family"]),
                "product_vt_symbol": product,
                "stage625_rows": int(row["rows"]),
                "stage625_fetched_ok_rows": int(row["fetched_ok_rows"]),
                "stage625_event_auto_monitor_rows": int(row["event_auto_monitor_rows"]),
                "stage625_total_bytes": int(row["total_bytes"]),
                "stage625_pit_received_dates": int(row["pit_received_dates"]),
                "stage625_history_selector_rows": int(row["history_selector_rows"]),
                "stage625_event_signal_ready_rows": int(row["event_signal_ready_rows"]),
                "stage626_probe_rows": float(product_probe["weighted_probe_rows"].sum()) if not product_probe.empty else 0.0,
                "stage626_route_ready_rows": float(product_probe["weighted_route_ready_rows"].sum()) if not product_probe.empty else 0.0,
                "stage626_http_412_rows": float(product_probe["weighted_http_412_rows"].sum()) if not product_probe.empty else 0.0,
                "stage626_http_404_rows": float(product_probe["weighted_http_404_rows"].sum()) if not product_probe.empty else 0.0,
                "source_delta": "public_source_improved_selector_locked",
                "source_blocker": "PIT_depth/live_TCA/predictive_signal"
                if product_probe.empty
                else "CZCE_route_blocked_plus_PIT_depth/live_TCA/predictive_signal",
            }
        )

    if product_rows:
        return pd.DataFrame(product_rows)
    return pd.DataFrame(
        columns=[
            "product_family",
            "product_vt_symbol",
            "stage625_rows",
            "stage625_fetched_ok_rows",
            "stage625_event_auto_monitor_rows",
            "stage625_total_bytes",
            "stage625_pit_received_dates",
            "stage625_history_selector_rows",
            "stage625_event_signal_ready_rows",
            "stage626_probe_rows",
            "stage626_route_ready_rows",
            "stage626_http_412_rows",
            "stage626_http_404_rows",
            "source_delta",
            "source_blocker",
        ]
    )


def build_family_reprioritization(priority: pd.DataFrame, source_delta: pd.DataFrame) -> pd.DataFrame:
    frame = priority.copy()
    frame["product_family"] = frame["product_family"].astype(str)
    frame["priority"] = frame["priority"].astype(str)
    frame["slot_role"] = frame["slot_role"].astype(str)
    frame["candidate_products"] = frame["candidate_products"].fillna("").astype(str)
    for column in [
        "max_abs_core_corr",
        "slot_total_pnl_sum",
        "readiness_score",
        "evidence_low_corr",
        "evidence_material",
        "evidence_source",
        "evidence_capacity_hint",
        "evidence_live_tca",
        "evidence_live_execution",
        "allowed_incremental_budget_now_pct",
        "conditional_effective_slot_count",
        "conditional_single_slot_risk_pct",
    ]:
        frame[column] = _num(frame, column)

    source = source_delta.copy()
    for column in [
        "stage625_fetched_ok_rows",
        "stage625_event_auto_monitor_rows",
        "stage625_total_bytes",
        "stage625_pit_received_dates",
        "stage625_history_selector_rows",
        "stage625_event_signal_ready_rows",
        "stage626_route_ready_rows",
        "stage626_http_412_rows",
        "stage626_http_404_rows",
    ]:
        source[column] = _num(source, column)

    source_family = (
        source.groupby("product_family", sort=False)
        .agg(
            source_products=("product_vt_symbol", lambda values: ",".join(map(str, values))),
            stage625_fetched_ok_rows=("stage625_fetched_ok_rows", "sum"),
            stage625_event_auto_monitor_rows=("stage625_event_auto_monitor_rows", "sum"),
            stage625_total_bytes=("stage625_total_bytes", "sum"),
            stage625_pit_received_dates_min=("stage625_pit_received_dates", "min"),
            stage625_history_selector_rows=("stage625_history_selector_rows", "sum"),
            stage625_event_signal_ready_rows=("stage625_event_signal_ready_rows", "sum"),
            stage626_route_ready_rows=("stage626_route_ready_rows", "sum"),
            stage626_http_412_rows=("stage626_http_412_rows", "sum"),
            stage626_http_404_rows=("stage626_http_404_rows", "sum"),
        )
        .reset_index()
    )
    merged = frame.merge(source_family, on="product_family", how="left")
    fill_columns = [
        "stage625_fetched_ok_rows",
        "stage625_event_auto_monitor_rows",
        "stage625_total_bytes",
        "stage625_pit_received_dates_min",
        "stage625_history_selector_rows",
        "stage625_event_signal_ready_rows",
        "stage626_route_ready_rows",
        "stage626_http_412_rows",
        "stage626_http_404_rows",
    ]
    for column in fill_columns:
        merged[column] = _num(merged, column)
    merged["source_products"] = merged["source_products"].fillna("")

    updated_priorities: list[str] = []
    updated_actions: list[str] = []
    slot_candidate_now: list[int] = []
    p2_promoted_to_p1: list[int] = []
    for _, row in merged.iterrows():
        family = row["product_family"]
        prev_priority = row["priority"]
        low_corr = row["max_abs_core_corr"] <= MAX_CORE_CORR_OBSERVE
        material = row["slot_total_pnl_sum"] > 0 and int(row["evidence_material"]) == 1
        source_improved = row["stage625_fetched_ok_rows"] > 0 or row["stage625_event_auto_monitor_rows"] > 0
        selector_still_locked = (
            row["stage625_history_selector_rows"] <= 0
            and row["stage625_event_signal_ready_rows"] <= 0
            and row["evidence_live_tca"] <= 0
            and row["evidence_live_execution"] <= 0
        )
        czce_route_blocked = row["stage626_http_412_rows"] > 0 or row["stage626_http_404_rows"] > 0

        if family == "black_ferrous":
            updated_priorities.append("P1")
            updated_actions.append("仍是唯一P1新增槽线索；source/TCA/live未闭合，新增预算为0。")
            slot_candidate_now.append(0)
            p2_promoted_to_p1.append(0)
        elif prev_priority == "P2" and source_improved and low_corr and not material:
            updated_priorities.append("P2+source")
            blocker = "CZCE路由失败，" if czce_route_blocked else ""
            updated_actions.append(f"{blocker}公开源证据增强但材料性/episode/selector/TCA不足，只能forward monitor。")
            slot_candidate_now.append(0)
            p2_promoted_to_p1.append(0)
        elif prev_priority == "P2" and source_improved and low_corr and material and selector_still_locked:
            updated_priorities.append("P2+edge_unverified")
            updated_actions.append("低相关且有材料性线索，但selector/TCA仍锁，不能给预算。")
            slot_candidate_now.append(0)
            p2_promoted_to_p1.append(0)
        else:
            updated_priorities.append(prev_priority)
            updated_actions.append(str(row.get("next_action", "")))
            slot_candidate_now.append(0)
            p2_promoted_to_p1.append(0)

    merged["updated_priority"] = updated_priorities
    merged["updated_action"] = updated_actions
    merged["slot_candidate_now"] = slot_candidate_now
    merged["p2_promoted_to_p1"] = p2_promoted_to_p1
    merged["allowed_incremental_budget_now_pct"] = 0.0
    merged["selector_or_whitelist_allowed"] = 0
    merged["rank_sort"] = merged["updated_priority"].map(
        {
            "P0": 0,
            "P1": 1,
            "P2+edge_unverified": 2,
            "P2+source": 3,
            "P2": 4,
            "Observe": 5,
            "Reject": 6,
        }
    ).fillna(9)
    merged = merged.sort_values(["rank_sort", "readiness_score", "slot_total_pnl_sum"], ascending=[True, False, False])
    return merged.drop(columns=["rank_sort"])


def build_scenarios(reprioritized: pd.DataFrame, annual: pd.DataFrame, holding: pd.DataFrame) -> pd.DataFrame:
    p2_source_families = sorted(
        reprioritized.loc[reprioritized["updated_priority"].astype(str).str.contains("P2", na=False), "product_family"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    p2_count = len(p2_source_families)
    deployable_no_degrade_count = int(_num(holding, "deployable_no_degrade_pass").sum()) if not holding.empty else 0
    years = int(annual["year"].nunique()) if "year" in annual.columns else 0
    after_black_capture_min = (
        float(_num(annual, "p0_plus_black_family_capture_pct").min()) if not annual.empty else 0.0
    )
    current_capture_min = (
        float(_num(annual, "current_p0_family_capture_pct").min()) if not annual.empty else 0.0
    )

    rows = [
        {
            "scenario": "current_p0_only",
            "effective_slots": CURRENT_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": _slot_risk(CURRENT_EFFECTIVE_SLOTS),
            "deployable_now": 0,
            "allowed_incremental_budget_pct": 0.0,
            "families": "current_P0",
            "interpretation": "当前只有4个结构槽，单槽风险约25%。",
        },
        {
            "scenario": "p0_plus_black_ferrous_if_closed",
            "effective_slots": SLOTS_IF_BLACK_CLOSED,
            "single_slot_risk_pct": _slot_risk(SLOTS_IF_BLACK_CLOSED),
            "deployable_now": 0,
            "allowed_incremental_budget_pct": 0.0,
            "families": "current_P0,black_ferrous",
            "interpretation": "black_ferrous闭合后也只有5槽，单槽风险约20%。",
        },
        {
            "scenario": "p0_plus_black_plus_p2_if_edge_verified",
            "effective_slots": SLOTS_IF_BLACK_CLOSED + p2_count,
            "single_slot_risk_pct": _slot_risk(SLOTS_IF_BLACK_CLOSED + p2_count),
            "deployable_now": 0,
            "allowed_incremental_budget_pct": 0.0,
            "families": "current_P0,black_ferrous," + ",".join(p2_source_families),
            "interpretation": "理论上到7槽，但P2没有材料性episode/selector/TCA，当前不能部署。",
        },
    ]
    scenarios = pd.DataFrame(rows)
    scenarios["target_slots"] = TARGET_EFFECTIVE_SLOTS
    scenarios["preferred_single_slot_risk_pct"] = PREFERRED_SINGLE_SLOT_RISK_PCT
    scenarios["deployable_no_degrade_count"] = deployable_no_degrade_count
    scenarios["annual_years"] = years
    scenarios["current_capture_min_pct"] = current_capture_min
    scenarios["after_black_capture_min_pct"] = after_black_capture_min
    return scenarios


def build_gates(reprioritized: pd.DataFrame, source_delta: pd.DataFrame, scenarios: pd.DataFrame) -> pd.DataFrame:
    p1_count = int((reprioritized["updated_priority"] == "P1").sum())
    p2_source_count = int(reprioritized["updated_priority"].astype(str).str.contains("P2\\+source", regex=True).sum())
    selector_rows = int(_num(source_delta, "stage625_history_selector_rows").sum() + _num(source_delta, "stage625_event_signal_ready_rows").sum())
    stage626_ready_rows = int(_num(source_delta, "stage626_route_ready_rows").sum())
    deployable_scenario_count = int(_num(scenarios, "deployable_now").sum())
    best_slots = int(_num(scenarios, "effective_slots").max())
    p2_promoted = int(_num(reprioritized, "p2_promoted_to_p1").sum())
    budget_sum = float(_num(reprioritized, "allowed_incremental_budget_now_pct").sum())

    rows = [
        {
            "gate": "incremental_budget_zero",
            "passed": int(budget_sum == 0.0),
            "current": f"{budget_sum:.2f}%",
            "required": "0%",
            "note": "source evidence must not be confused with deployable risk budget.",
        },
        {
            "gate": "selector_or_event_signal_still_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "Stage625 source rows do not enter history selector or event signal.",
        },
        {
            "gate": "czce_route_ready_zero_after_forensic",
            "passed": int(stage626_ready_rows == 0),
            "current": stage626_ready_rows,
            "required": 0,
            "note": "Stage626 confirms CZCE static/reference route remains blocked.",
        },
        {
            "gate": "p2_source_improved_but_not_promoted",
            "passed": int(p2_source_count >= 1 and p2_promoted == 0),
            "current": f"P2+source={p2_source_count}, promoted={p2_promoted}",
            "required": "source improved and promotion 0",
            "note": "public source monitor can improve without becoming a selector.",
        },
        {
            "gate": "p1_slots_still_less_than_needed",
            "passed": int(p1_count < 3),
            "current": p1_count,
            "required": "<3 until two more P1 slots found",
            "note": "black_ferrous remains the only P1 new-slot line.",
        },
        {
            "gate": "hypothetical_slots_can_reach_7_only_with_p2",
            "passed": int(best_slots >= TARGET_EFFECTIVE_SLOTS),
            "current": best_slots,
            "required": TARGET_EFFECTIVE_SLOTS,
            "note": "the structural target is plausible only if P2 families earn edge/TCA status.",
        },
        {
            "gate": "deployable_scenarios_zero",
            "passed": int(deployable_scenario_count == 0),
            "current": deployable_scenario_count,
            "required": 0,
            "note": "no scenario can be deployed now because live TCA/predictive evidence is absent.",
        },
        {
            "gate": "preferred_slot_risk_not_reached_by_deployable_slots",
            "passed": int(SLOTS_IF_BLACK_CLOSED < TARGET_EFFECTIVE_SLOTS),
            "current": f"{_slot_risk(SLOTS_IF_BLACK_CLOSED):.2f}%",
            "required": f"<={PREFERRED_SINGLE_SLOT_RISK_PCT:.2f}% deployable",
            "note": "even closing black_ferrous leaves single-slot risk around 20%.",
        },
    ]
    return pd.DataFrame(rows)


def write_report(
    generated_at: datetime,
    reprioritized: pd.DataFrame,
    source_delta: pd.DataFrame,
    scenarios: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage627 Post Source Probe Slot Reprioritization",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: read-only reprioritization; no strategy replay, no selector, no paper whitelist, no CTP/order path.",
        "",
        "## External Research And Judgement",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "Judgement:",
        "- Diversified trend following should be evaluated by independent risk slots and stress correlation, not by product count.",
        "- Source readiness is necessary for live execution, but source readiness alone is not evidence of predictive edge.",
        "- The latest Stage625/626 evidence should update monitoring priority, not unlock risk budget.",
        "",
        "## Key Results",
        "",
        f"- P1 new-slot families now: `{decision['p1_new_slot_family_count']}`",
        f"- P2 source-improved families now: `{decision['p2_source_improved_family_count']}`",
        f"- deployable new slots now: `{decision['deployable_new_slots_now']}`",
        f"- best hypothetical slots if P2 edge later verified: `{decision['best_hypothetical_slots']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Family Reprioritization",
        "",
        _md_table(
            reprioritized,
            [
                "updated_priority",
                "product_family",
                "candidate_products",
                "slot_role",
                "max_abs_core_corr",
                "slot_total_pnl_sum",
                "stage625_fetched_ok_rows",
                "stage625_event_auto_monitor_rows",
                "stage626_http_412_rows",
                "stage626_http_404_rows",
                "updated_action",
            ],
            max_rows=20,
        ),
        "",
        "## Source Delta",
        "",
        _md_table(source_delta, max_rows=20),
        "",
        "## Slot Scenarios",
        "",
        _md_table(scenarios, max_rows=10),
        "",
        "## Gates",
        "",
        _md_table(gates, max_rows=20),
        "",
        "## Visual Review Checklist",
        "",
        "- Top-left: scenario bars must show the difference between current deployable slots and hypothetical slots.",
        "- Top-right: scatter should make high-correlation winners visually obvious rather than hiding them in aggregate scores.",
        "- Bottom-left: source matrix must distinguish public-source success from selector/TCA readiness.",
        "- Bottom-right: failed gates should remain visibly red when deployment is locked.",
        "",
        "## Output Files",
        "",
        f"- family reprioritization: `{FAMILY_REPRIORITIZATION_PATH}`",
        f"- source delta: `{SOURCE_DELTA_PATH}`",
        f"- scenarios: `{SCENARIO_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- chart: `{CHART_PATH}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def plot_chart(reprioritized: pd.DataFrame, source_delta: pd.DataFrame, scenarios: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12), constrained_layout=True)
    fig.suptitle("Stage627 post-source-probe risk-slot reprioritization: monitor improved, budget locked", fontsize=16)

    ax = axes[0, 0]
    colors = ["#4c78a8" if row["deployable_now"] else "#f58518" for _, row in scenarios.iterrows()]
    scenario_labels = ["current", "black closed", "black+P2 verified"]
    ax.bar(scenario_labels, scenarios["effective_slots"], color=colors)
    ax.axhline(TARGET_EFFECTIVE_SLOTS, color="#e45756", linestyle="--", linewidth=1.5, label="target 7 slots")
    for idx, row in scenarios.reset_index(drop=True).iterrows():
        ax.text(idx, row["effective_slots"] + 0.08, f"{int(row['effective_slots'])} slots\n{row['single_slot_risk_pct']:.1f}%/slot", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("effective slots")
    ax.set_title("Slot ladder: deployable vs hypothetical")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(loc="upper left")

    ax = axes[0, 1]
    priority_colors = {
        "P0": "#4c78a8",
        "P1": "#54a24b",
        "P2+source": "#f58518",
        "P2+edge_unverified": "#ffbf79",
        "P2": "#f58518",
        "Observe": "#bab0ac",
        "Reject": "#e45756",
    }
    for _, row in reprioritized.iterrows():
        priority = str(row["updated_priority"])
        ax.scatter(
            row["max_abs_core_corr"],
            row["slot_total_pnl_sum"],
            s=120 + 40 * float(row.get("stage625_fetched_ok_rows", 0)),
            color=priority_colors.get(priority, "#79706e"),
            alpha=0.85,
            edgecolor="black",
            linewidth=0.6,
        )
        family = str(row["product_family"])
        offsets = {
            "precious_metals": (0.006, -2800),
            "soft_agri": (0.006, 1200),
            "financial_index": (0.006, 2600),
            "livestock": (0.006, -2200),
            "black_ferrous": (0.006, 1200),
            "base_metals": (0.006, -1800),
        }
        dx, dy = offsets.get(family, (0.004, 0))
        ax.text(row["max_abs_core_corr"] + dx, row["slot_total_pnl_sum"] + dy, family, fontsize=8, va="center")
    ax.axvline(MAX_CORE_CORR_OBSERVE, color="#e45756", linestyle="--", linewidth=1.2, label="corr observe line")
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("max abs core corr")
    ax.set_ylabel("slot total pnl proxy")
    ax.set_title("Family priority: low corr is not enough without material edge")
    ax.legend(loc="best")

    ax = axes[1, 0]
    families = reprioritized["product_family"].astype(str).tolist()
    matrix_columns = [
        "source_ok",
        "event_monitor",
        "czce_blocked",
        "selector_ready",
        "live_tca",
        "budget_allowed",
    ]
    matrix = []
    for _, row in reprioritized.iterrows():
        matrix.append(
            [
                1 if row["stage625_fetched_ok_rows"] > 0 or row.get("evidence_source", 0) > 0 else 0,
                1 if row["stage625_event_auto_monitor_rows"] > 0 else 0,
                -1 if row["stage626_http_412_rows"] > 0 or row["stage626_http_404_rows"] > 0 else 0,
                1 if row["stage625_history_selector_rows"] > 0 or row["stage625_event_signal_ready_rows"] > 0 else 0,
                1 if row.get("evidence_live_tca", 0) > 0 else 0,
                1 if row["allowed_incremental_budget_now_pct"] > 0 else 0,
            ]
        )
    matrix_arr = np.array(matrix, dtype=float)
    cmap = matplotlib.colors.ListedColormap(["#e45756", "#f1f1f1", "#54a24b"])
    norm = matplotlib.colors.BoundaryNorm([-1.5, -0.5, 0.5, 1.5], cmap.N)
    ax.imshow(matrix_arr, cmap=cmap, norm=norm, aspect="auto")
    ax.set_yticks(np.arange(len(families)))
    ax.set_yticklabels(families)
    ax.set_xticks(np.arange(len(matrix_columns)))
    ax.set_xticklabels(matrix_columns, rotation=30, ha="right")
    for i in range(matrix_arr.shape[0]):
        for j in range(matrix_arr.shape[1]):
            label = "BLOCK" if matrix_arr[i, j] < 0 else ("OK" if matrix_arr[i, j] > 0 else "0")
            ax.text(j, i, label, ha="center", va="center", fontsize=8, color="black")
    ax.set_title("Evidence matrix: source success does not equal selector readiness")

    ax = axes[1, 1]
    gate_colors = ["#54a24b" if bool(row["passed"]) else "#e45756" for _, row in gates.iterrows()]
    ax.barh(gates["gate"], [1] * len(gates), color=gate_colors)
    for idx, row in gates.reset_index(drop=True).iterrows():
        ax.text(0.02, idx, str(row["current"]), va="center", ha="left", color="white", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Fail-closed audit gates (green = lock discipline held)")

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    generated_at = _now_cst()
    annual = _read_csv(STAGE604_ANNUAL_CAPTURE)
    holding = _read_csv(STAGE604_HOLDING_BOUNDARY)
    priority = _read_csv(STAGE621_FAMILY_PRIORITY)
    _ = _read_csv(STAGE621_SLOT_LADDER)
    stage625_raw = _read_csv(STAGE625_RAW_LEDGER)
    stage625_product = _read_csv(STAGE625_PRODUCT_SUMMARY)
    stage626_probe = _read_csv(STAGE626_PROBE_LEDGER)

    source_delta = build_source_delta(stage625_product, stage625_raw, stage626_probe)
    reprioritized = build_family_reprioritization(priority, source_delta)
    scenarios = build_scenarios(reprioritized, annual, holding)
    gates = build_gates(reprioritized, source_delta, scenarios)

    p1_count = int((reprioritized["updated_priority"] == "P1").sum())
    p2_source_count = int(reprioritized["updated_priority"].astype(str).str.contains("P2\\+source", regex=True).sum())
    deployable_new_slots_now = int(_num(reprioritized, "slot_candidate_now").sum())
    best_hypothetical_slots = int(_num(scenarios, "effective_slots").max())
    hard_gates_passed = int(_num(gates, "passed").sum())
    hard_gates_total = int(len(gates))
    decision_label = (
        "source_probe_reprioritizes_p2_monitor_no_new_slot_budget"
        if p2_source_count > 0 and deployable_new_slots_now == 0
        else "source_probe_no_priority_change_no_new_slot_budget"
    )
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": decision_label,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "p1_new_slot_family_count": p1_count,
        "p2_source_improved_family_count": p2_source_count,
        "deployable_new_slots_now": deployable_new_slots_now,
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "slots_if_black_ferrous_closed": SLOTS_IF_BLACK_CLOSED,
        "best_hypothetical_slots": best_hypothetical_slots,
        "single_slot_risk_current_pct": _slot_risk(CURRENT_EFFECTIVE_SLOTS),
        "single_slot_risk_if_black_closed_pct": _slot_risk(SLOTS_IF_BLACK_CLOSED),
        "single_slot_risk_if_hypothetical_p2_verified_pct": _slot_risk(best_hypothetical_slots),
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "summary": (
            "Stage625 improves public-source monitor evidence for ag/CY/SR and Stage626 confirms CZCE route blocks; "
            "this upgrades P2 monitoring clarity but does not create a deployable new risk slot."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reprioritized.to_csv(FAMILY_REPRIORITIZATION_PATH, index=False, encoding="utf-8-sig")
    source_delta.to_csv(SOURCE_DELTA_PATH, index=False, encoding="utf-8-sig")
    scenarios.to_csv(SCENARIO_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(generated_at, reprioritized, source_delta, scenarios, gates, decision)
    plot_chart(reprioritized, source_delta, scenarios, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
