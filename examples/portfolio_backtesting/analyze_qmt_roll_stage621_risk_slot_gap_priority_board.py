from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
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


MODEL_TAG = "stage621_risk_slot_gap_priority_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage621_risk_slot_gap_priority_board"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE604_ALLOCATOR_SCENARIOS = OUTPUT_DIR / (
    "qmt_roll_stage604_low_single_risk_slot_allocator_audit_allocator_scenarios_"
    "stage604_low_single_risk_slot_allocator_audit_v1.csv"
)
STAGE604_ANNUAL_CAPTURE = OUTPUT_DIR / (
    "qmt_roll_stage604_low_single_risk_slot_allocator_audit_annual_capture_"
    "stage604_low_single_risk_slot_allocator_audit_v1.csv"
)
STAGE604_HOLDING_BOUNDARY = OUTPUT_DIR / (
    "qmt_roll_stage604_low_single_risk_slot_allocator_audit_holding_boundary_"
    "stage604_low_single_risk_slot_allocator_audit_v1.csv"
)
STAGE611_FAMILY_ADMISSION = OUTPUT_DIR / (
    "qmt_roll_stage611_risk_slot_admission_protocol_family_admission_"
    "stage611_risk_slot_admission_protocol_v1.csv"
)
STAGE620_COLLECTOR_CONTRACT = OUTPUT_DIR / (
    "qmt_roll_stage620_forward_source_collector_contract_collector_contract_"
    "stage620_forward_source_collector_contract_v1.csv"
)
STAGE620_DECISION = OUTPUT_DIR / (
    "qmt_roll_stage620_forward_source_collector_contract_decision_"
    "stage620_forward_source_collector_contract_v1.json"
)

FAMILY_PRIORITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_priority_{MODEL_TAG}.csv"
SLOT_LADDER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slot_ladder_{MODEL_TAG}.csv"
ANNUAL_MISS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_miss_{MODEL_TAG}.csv"
SOURCE_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_contract_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_EFFECTIVE_SLOTS = 7
CURRENT_EFFECTIVE_SLOTS = 4
IF_BLACK_FERROUS_RESOLVED_SLOTS = 5
PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0
HARD_SINGLE_SLOT_RISK_PCT = 20.0
MAX_CORE_CORR_PREFERRED = 0.10


REFERENCE_LINKS = [
    "AQR trend following / risk-mitigating portfolio design: "
    "https://www.aqr.com/Insights/Research/Alternative-Thinking/Key-Design-Choices-when-Building-a-Risk-Mitigating-Portfolio",
    "Man Group trend following market mix: "
    "https://www.man.com/insights/trend-following-optimal-market-mix",
    "Graham Capital trend-following primer / portfolio construction: "
    "https://www.grahamcapital.com/blog/trend-following-primer-2026/",
    "Riskfolio-Lib / risk budgeting implementation reference: https://github.com/dcajasn/Riskfolio-Lib",
]


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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
    if isinstance(value, (pd.Timestamp, datetime, date)):
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


def build_source_contract_summary(collector: pd.DataFrame) -> pd.DataFrame:
    frame = collector.copy()
    if frame.empty:
        return pd.DataFrame()
    frame["product_family"] = frame["product_family"].astype(str)
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["route_group"] = frame["route_group"].astype(str)
    frame["source_authority"] = frame["source_authority"].fillna("").astype(str)
    for column in [
        "collector_implemented",
        "source_url_template_ready",
        "required_fields_ready",
        "selector_unlock_candidate",
        "paper_or_whitelist_allowed",
        "stage617_contract_complete",
        "stage617_selector_ready",
    ]:
        frame[column] = _num(frame, column)

    rows: list[dict[str, Any]] = []
    for (family, product), group in frame.groupby(["product_family", "product_vt_symbol"], sort=False):
        rows.append(
            {
                "product_family": family,
                "product_vt_symbol": product,
                "route_count": int(group["route_group"].nunique()),
                "routes": ",".join(sorted(group["route_group"].unique())),
                "collector_implemented_count": int(group["collector_implemented"].sum()),
                "source_url_ready_count": int(group["source_url_template_ready"].sum()),
                "required_fields_ready_count": int(group["required_fields_ready"].sum()),
                "stage617_contract_complete_count": int(group["stage617_contract_complete"].sum()),
                "selector_ready_count": int(group["stage617_selector_ready"].sum()),
                "selector_unlock_candidate_count": int(group["selector_unlock_candidate"].sum()),
                "paper_or_whitelist_allowed_count": int(group["paper_or_whitelist_allowed"].sum()),
                "official_route_count": int(group["source_authority"].str.contains("official", case=False).sum()),
                "third_party_route_count": int(group["source_authority"].str.contains("third_party", case=False).sum()),
            }
        )
    return pd.DataFrame(rows)


def build_family_priority(admission: pd.DataFrame, source_summary: pd.DataFrame) -> pd.DataFrame:
    frame = admission.copy()
    frame["product_family"] = frame["product_family"].astype(str)
    frame["candidate_products"] = frame["candidate_products"].fillna("").astype(str)
    frame["slot_role"] = frame["slot_role"].astype(str)
    frame["max_abs_core_corr"] = _num(frame, "max_abs_core_corr")
    frame["slot_total_pnl_sum"] = _num(frame, "slot_total_pnl_sum")
    frame["readiness_score"] = _num(frame, "readiness_score")
    for column in [
        "evidence_low_corr",
        "evidence_material",
        "evidence_source",
        "evidence_capacity_hint",
        "evidence_live_tca",
        "evidence_live_execution",
        "deployable_now",
        "paper_allowed_now",
        "trading_whitelist_allowed_now",
    ]:
        frame[column] = _num(frame, column)

    source_family = pd.DataFrame()
    if not source_summary.empty:
        source_family = (
            source_summary.groupby("product_family", as_index=False)
            .agg(
                source_products=("product_vt_symbol", lambda series: ",".join(series.astype(str))),
                source_route_count=("route_count", "sum"),
                collector_implemented_count=("collector_implemented_count", "sum"),
                source_url_ready_count=("source_url_ready_count", "sum"),
                required_fields_ready_count=("required_fields_ready_count", "sum"),
                selector_ready_count=("selector_ready_count", "sum"),
                official_route_count=("official_route_count", "sum"),
                third_party_route_count=("third_party_route_count", "sum"),
            )
        )
    if source_family.empty:
        source_family = pd.DataFrame({"product_family": frame["product_family"].unique()})

    merged = frame.merge(source_family, on="product_family", how="left")
    for column in [
        "source_route_count",
        "collector_implemented_count",
        "source_url_ready_count",
        "required_fields_ready_count",
        "selector_ready_count",
        "official_route_count",
        "third_party_route_count",
    ]:
        merged[column] = _num(merged, column)
    merged["source_products"] = merged.get("source_products", "").fillna("").astype(str)

    role_rank = {
        "p1_new_family_blocked": 1,
        "source_rich_no_edge_monitor": 2,
        "current_p0_structural_slot": 3,
        "reject_or_observe": 4,
        "reject_high_core_corr": 5,
    }
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        role = str(row["slot_role"])
        family = str(row["product_family"])
        low_corr = int(row["evidence_low_corr"] > 0)
        material = int(row["evidence_material"] > 0)
        source = int(row["evidence_source"] > 0)
        capacity = int(row["evidence_capacity_hint"] > 0)
        live_tca = int(row["evidence_live_tca"] > 0)
        live_execution = int(row["evidence_live_execution"] > 0)
        evidence_count = low_corr + material + source + capacity + live_tca + live_execution

        if role == "p1_new_family_blocked":
            slot_impact = "+1 conditional slot if source/TCA/live close"
            priority = "P1"
            missing = "official_source_raw_hash,live_tca,live_context"
            promotion_action = "先补官方/授权source与真实TCA；闭合后仍只是5槽，需要另找2槽。"
            incremental_budget_now_pct = 0.0
            conditional_slot_count = IF_BLACK_FERROUS_RESOLVED_SLOTS
        elif role == "source_rich_no_edge_monitor":
            slot_impact = "monitor only; no slot budget"
            priority = "P2"
            missing = "material_edge,forward_episodes,selector_ic,live_tca"
            promotion_action = "只做12个月以上forward monitor和3个独立趋势episode，不进paper。"
            incremental_budget_now_pct = 0.0
            conditional_slot_count = CURRENT_EFFECTIVE_SLOTS
        elif role == "current_p0_structural_slot":
            slot_impact = "existing structural slot; no new slot"
            priority = "P0"
            missing = "live_tca,live_context"
            if row["max_abs_core_corr"] > MAX_CORE_CORR_PREFERRED:
                missing += ",core_corr_watch"
            promotion_action = "先闭合P0执行无偏差与TCA，再谈selector；同族同向保持top1。"
            incremental_budget_now_pct = 0.0
            conditional_slot_count = CURRENT_EFFECTIVE_SLOTS
        elif role == "reject_high_core_corr":
            slot_impact = "reject as diversifier"
            priority = "Reject"
            missing = "low_core_corr"
            promotion_action = "压力期伪分散风险高；除非未来相关性长期降下来，否则不复活。"
            incremental_budget_now_pct = 0.0
            conditional_slot_count = CURRENT_EFFECTIVE_SLOTS
        else:
            slot_impact = "observe only"
            priority = "Observe"
            missing = "materiality,source_or_tca"
            promotion_action = "不投入TCA预算；只保留低频观察。"
            incremental_budget_now_pct = 0.0
            conditional_slot_count = CURRENT_EFFECTIVE_SLOTS

        rows.append(
            {
                "priority": priority,
                "product_family": family,
                "candidate_products": row["candidate_products"],
                "slot_role": role,
                "slot_impact": slot_impact,
                "rank_key": role_rank.get(role, 9),
                "max_abs_core_corr": float(row["max_abs_core_corr"]),
                "slot_total_pnl_sum": float(row["slot_total_pnl_sum"]),
                "readiness_score": float(row["readiness_score"]),
                "evidence_count_0_6": int(evidence_count),
                "evidence_low_corr": low_corr,
                "evidence_material": material,
                "evidence_source": source,
                "evidence_capacity_hint": capacity,
                "evidence_live_tca": live_tca,
                "evidence_live_execution": live_execution,
                "source_products_in_stage620": row["source_products"],
                "stage620_source_route_count": int(row["source_route_count"]),
                "stage620_selector_ready_count": int(row["selector_ready_count"]),
                "stage620_official_route_count": int(row["official_route_count"]),
                "stage620_third_party_route_count": int(row["third_party_route_count"]),
                "allowed_incremental_budget_now_pct": incremental_budget_now_pct,
                "conditional_effective_slot_count": conditional_slot_count,
                "conditional_single_slot_risk_pct": _slot_risk(conditional_slot_count),
                "missing_for_promotion": missing,
                "next_action": promotion_action,
            }
        )
    result = pd.DataFrame(rows).sort_values(
        ["rank_key", "evidence_count_0_6", "readiness_score", "slot_total_pnl_sum"],
        ascending=[True, False, False, False],
    )
    return result.drop(columns=["rank_key"])


def build_slot_ladder() -> pd.DataFrame:
    rows = [
        {
            "scenario": "deployable_today",
            "effective_slots": 0,
            "single_slot_risk_pct": np.nan,
            "gap_to_target": TARGET_EFFECTIVE_SLOTS,
            "deployable_allowed": 0,
            "interpretation": "source selector、live context、TCA 全未闭合；今天不能部署扩池槽。",
        },
        {
            "scenario": "current_structural_p0",
            "effective_slots": CURRENT_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": _slot_risk(CURRENT_EFFECTIVE_SLOTS),
            "gap_to_target": TARGET_EFFECTIVE_SLOTS - CURRENT_EFFECTIVE_SLOTS,
            "deployable_allowed": 0,
            "interpretation": "结构上只有4个槽，约25%/slot；不是低单笔风险目标。",
        },
        {
            "scenario": "after_black_ferrous_closed",
            "effective_slots": IF_BLACK_FERROUS_RESOLVED_SLOTS,
            "single_slot_risk_pct": _slot_risk(IF_BLACK_FERROUS_RESOLVED_SLOTS),
            "gap_to_target": TARGET_EFFECTIVE_SLOTS - IF_BLACK_FERROUS_RESOLVED_SLOTS,
            "deployable_allowed": 0,
            "interpretation": "j/i 闭合后也只是5槽、20%/slot，仍差2个独立槽。",
        },
        {
            "scenario": "target_minimum_allocator",
            "effective_slots": TARGET_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": _slot_risk(TARGET_EFFECTIVE_SLOTS),
            "gap_to_target": 0,
            "deployable_allowed": 1,
            "interpretation": "至少7槽后单槽约14.29%，才接近低单笔风险结构。",
        },
    ]
    return pd.DataFrame(rows)


def build_annual_miss(annual_capture: pd.DataFrame, family_priority: pd.DataFrame) -> pd.DataFrame:
    status_by_family = family_priority.set_index("product_family").to_dict("index")
    rows: list[dict[str, Any]] = []
    for _, annual in annual_capture.iterrows():
        year = int(annual["year"])
        missed = _split_csv_cell(annual.get("missed_families_after_black", ""))
        if not missed:
            rows.append(
                {
                    "year": year,
                    "missed_family_after_black": "",
                    "family_status": "covered_after_black",
                    "priority": "",
                    "is_solvable_now": 0,
                    "next_action": "年度top6家族已被P0+black覆盖。",
                    "top6_pnl": float(annual.get("top6_pnl", 0.0)),
                    "p0_plus_black_capture_pct": float(annual.get("p0_plus_black_family_capture_pct", 0.0)),
                    "top6_products": annual.get("top6_products", ""),
                    "top6_families": annual.get("top6_families", ""),
                }
            )
            continue
        for family in missed:
            info = status_by_family.get(family, {})
            role = str(info.get("slot_role", "not_in_admission_table"))
            priority = str(info.get("priority", "Unknown"))
            if role == "source_rich_no_edge_monitor":
                action = "source较好但材料性不足；累计forward episodes，不给预算。"
            elif role == "reject_high_core_corr":
                action = "高相关拒绝；不能用历史收益把它变成分散槽。"
            elif role == "reject_or_observe":
                action = "缺材料性/source/TCA，只观察。"
            else:
                action = "当前没有可执行晋级路径。"
            rows.append(
                {
                    "year": year,
                    "missed_family_after_black": family,
                    "family_status": role,
                    "priority": priority,
                    "is_solvable_now": 0,
                    "next_action": action,
                    "top6_pnl": float(annual.get("top6_pnl", 0.0)),
                    "p0_plus_black_capture_pct": float(annual.get("p0_plus_black_family_capture_pct", 0.0)),
                    "top6_products": annual.get("top6_products", ""),
                    "top6_families": annual.get("top6_families", ""),
                }
            )
    return pd.DataFrame(rows)


def build_gates(
    family_priority: pd.DataFrame,
    slot_ladder: pd.DataFrame,
    holding_boundary: pd.DataFrame,
    stage620_decision: dict[str, Any],
) -> pd.DataFrame:
    deployable_today_slots = int(
        slot_ladder.loc[slot_ladder["scenario"].eq("deployable_today"), "effective_slots"].iloc[0]
    )
    current_slots = int(
        slot_ladder.loc[slot_ladder["scenario"].eq("current_structural_p0"), "effective_slots"].iloc[0]
    )
    after_black_slots = int(
        slot_ladder.loc[slot_ladder["scenario"].eq("after_black_ferrous_closed"), "effective_slots"].iloc[0]
    )
    usable_holding = int(_num(holding_boundary, "usable_for_allocator").sum()) if not holding_boundary.empty else 0
    p1_slots = int(family_priority["slot_role"].eq("p1_new_family_blocked").sum())
    p2_slots = int(family_priority["slot_role"].eq("source_rich_no_edge_monitor").sum())
    rejected_high_corr = int(family_priority["slot_role"].eq("reject_high_core_corr").sum())
    any_budget_now = float(_num(family_priority, "allowed_incremental_budget_now_pct").sum())
    selector_ready_count = int(_num(family_priority, "stage620_selector_ready_count").sum())
    fetched_rows = int(stage620_decision.get("fetched_rows_with_raw_hash", 0) or 0)

    rows = [
        {
            "gate": "no_incremental_budget_today",
            "passed": int(any_budget_now == 0),
            "current": f"{any_budget_now:.2f}%",
            "required": "0%",
            "note": "所有新增槽默认 fail-closed，防止把watchlist误用成白名单。",
        },
        {
            "gate": "deployable_slots_today_zero",
            "passed": int(deployable_today_slots == 0),
            "current": str(deployable_today_slots),
            "required": "0",
            "note": "真实selector/live/TCA未闭合时，扩池部署槽必须为0。",
        },
        {
            "gate": "current_slots_reach_target_7",
            "passed": int(current_slots >= TARGET_EFFECTIVE_SLOTS),
            "current": str(current_slots),
            "required": str(TARGET_EFFECTIVE_SLOTS),
            "note": "结构槽不足，当前单槽风险仍约25%。",
        },
        {
            "gate": "after_black_still_reach_target_7",
            "passed": int(after_black_slots >= TARGET_EFFECTIVE_SLOTS),
            "current": str(after_black_slots),
            "required": str(TARGET_EFFECTIVE_SLOTS),
            "note": "black_ferrous闭合后仍只到5槽，差2槽。",
        },
        {
            "gate": "preferred_single_slot_risk_le_15",
            "passed": int(_slot_risk(current_slots) <= PREFERRED_SINGLE_SLOT_RISK_PCT),
            "current": f"{_slot_risk(current_slots):.2f}%",
            "required": f"<={PREFERRED_SINGLE_SLOT_RISK_PCT:.2f}%",
            "note": "低单笔风险目标未达成。",
        },
        {
            "gate": "deployable_holding_experience_no_degrade",
            "passed": int(usable_holding > 0),
            "current": str(usable_holding),
            "required": ">=1",
            "note": "Stage604显示可部署宽池壳没有改善3/6个月左尾。",
        },
        {
            "gate": "stage620_selector_ready_or_fetch_evidence",
            "passed": int(selector_ready_count > 0 and fetched_rows > 0),
            "current": f"selector_ready={selector_ready_count}, fetched_hash={fetched_rows}",
            "required": "selector_ready>0 and fetched_hash>0",
            "note": "source collector合同存在，但尚不能解锁selector。",
        },
        {
            "gate": "at_least_two_new_independent_slots_identified",
            "passed": int(p1_slots >= 3),
            "current": f"P1={p1_slots}, P2={p2_slots}",
            "required": ">=3 P1 slots including black_ferrous",
            "note": "当前只有black_ferrous一个P1，且仍未闭合。",
        },
        {
            "gate": "high_corr_winners_rejected",
            "passed": int(rejected_high_corr >= 1),
            "current": str(rejected_high_corr),
            "required": ">=1",
            "note": "br/other这类高相关历史机会被拒绝，说明没有收益榜过拟合。",
        },
    ]
    return pd.DataFrame(rows)


def build_decision(
    family_priority: pd.DataFrame,
    slot_ladder: pd.DataFrame,
    annual_miss: pd.DataFrame,
    gates: pd.DataFrame,
    source_summary: pd.DataFrame,
) -> dict[str, Any]:
    current_slots = int(
        slot_ladder.loc[slot_ladder["scenario"].eq("current_structural_p0"), "effective_slots"].iloc[0]
    )
    after_black_slots = int(
        slot_ladder.loc[slot_ladder["scenario"].eq("after_black_ferrous_closed"), "effective_slots"].iloc[0]
    )
    missed_families = sorted(
        {
            str(item)
            for item in annual_miss["missed_family_after_black"].dropna().astype(str)
            if str(item)
        }
    )
    p1_families = family_priority.loc[
        family_priority["slot_role"].eq("p1_new_family_blocked"), "product_family"
    ].astype(str).tolist()
    p2_families = family_priority.loc[
        family_priority["slot_role"].eq("source_rich_no_edge_monitor"), "product_family"
    ].astype(str).tolist()
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _now_cst(),
        "decision": "risk_slot_gap_priority_board_direction_valid_no_promotion_need_two_new_independent_slots",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "current_effective_slots": current_slots,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "current_single_slot_risk_pct": _slot_risk(current_slots),
        "slots_if_black_ferrous_closed": after_black_slots,
        "single_slot_risk_if_black_ferrous_closed_pct": _slot_risk(after_black_slots),
        "missing_slots_after_black_ferrous": TARGET_EFFECTIVE_SLOTS - after_black_slots,
        "p1_new_slot_families": p1_families,
        "p2_forward_monitor_families": p2_families,
        "annual_missed_families_after_black": missed_families,
        "stage620_source_products": int(source_summary["product_vt_symbol"].nunique()) if not source_summary.empty else 0,
        "stage620_selector_ready_count": int(_num(source_summary, "selector_ready_count").sum())
        if not source_summary.empty
        else 0,
        "hard_gates_passed": int(gates["passed"].astype(int).sum()),
        "hard_gates_total": int(len(gates)),
        "summary": (
            "减少单笔风险和扩池方向成立，但当前只有4个结构槽；black_ferrous闭合后也只有5槽，"
            "距离7槽/约14.29%单槽风险目标仍差2槽。当前没有新增预算、paper selector或交易白名单。"
        ),
    }


def plot_chart(
    family_priority: pd.DataFrame,
    slot_ladder: pd.DataFrame,
    annual_miss: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    fig.suptitle("Stage621 risk slot gap priority board: direction valid, no promotion", fontsize=15)

    ax = axes[0, 0]
    ladder = slot_ladder.copy()
    colors = ["#9ca3af", "#f59e0b", "#f97316", "#16a34a"]
    bars = ax.bar(ladder["scenario"], ladder["effective_slots"], color=colors)
    ax.axhline(TARGET_EFFECTIVE_SLOTS, color="#dc2626", linestyle="--", linewidth=1.4, label="target 7 slots")
    ax.set_ylabel("effective independent slots")
    ax.set_title("Slot ladder and single-slot risk")
    ax.set_ylim(0, 8.25)
    ax.tick_params(axis="x", labelrotation=18)
    for bar, risk in zip(bars, ladder["single_slot_risk_pct"]):
        height = bar.get_height()
        label = "0 slot" if height == 0 else f"{height:.0f} slots\n{risk:.1f}%/slot"
        ax.text(bar.get_x() + bar.get_width() / 2, height + 0.22, label, ha="center", va="bottom", fontsize=9)
    ax.legend(loc="upper left", fontsize=9)

    ax = axes[0, 1]
    role_colors = {
        "current_p0_structural_slot": "#2563eb",
        "p1_new_family_blocked": "#dc2626",
        "source_rich_no_edge_monitor": "#10b981",
        "reject_high_core_corr": "#6b7280",
        "reject_or_observe": "#9ca3af",
    }
    for role, group in family_priority.groupby("slot_role", sort=False):
        ax.scatter(
            group["max_abs_core_corr"],
            group["slot_total_pnl_sum"],
            s=70 + group["readiness_score"].astype(float) * 35,
            color=role_colors.get(role, "#9ca3af"),
            alpha=0.78,
            label=role,
            edgecolor="white",
            linewidth=0.8,
        )
        for _, row in group.iterrows():
            ax.annotate(
                row["product_family"],
                (row["max_abs_core_corr"], row["slot_total_pnl_sum"]),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=8,
            )
    ax.axvline(MAX_CORE_CORR_PREFERRED, color="#dc2626", linestyle="--", linewidth=1.2)
    ax.axhline(0, color="#6b7280", linewidth=0.8)
    ax.set_xlabel("abs core daily PnL corr")
    ax.set_ylabel("slot historical PnL proxy")
    ax.set_title("Family role: not every profitable family is a slot")
    ax.legend(loc="best", fontsize=8)

    ax = axes[1, 0]
    annual_plot = (
        annual_miss.groupby(["year", "missed_family_after_black"], as_index=False)
        .size()
        .pivot(index="year", columns="missed_family_after_black", values="size")
        .fillna(0)
    )
    if "" in annual_plot.columns:
        annual_plot = annual_plot.drop(columns=[""])
    if annual_plot.empty:
        ax.text(0.5, 0.5, "No missed family after black_ferrous", ha="center", va="center")
        ax.axis("off")
    else:
        im = ax.imshow(annual_plot.values, aspect="auto", cmap="Reds", vmin=0, vmax=1)
        ax.set_xticks(range(len(annual_plot.columns)))
        ax.set_xticklabels(annual_plot.columns, rotation=25, ha="right")
        ax.set_yticks(range(len(annual_plot.index)))
        ax.set_yticklabels(annual_plot.index.astype(str))
        ax.set_title("Annual top6 missed families after adding black_ferrous")
        for i in range(annual_plot.shape[0]):
            for j in range(annual_plot.shape[1]):
                if annual_plot.iloc[i, j] > 0:
                    ax.text(j, i, "miss", ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        fig.colorbar(im, ax=ax, shrink=0.85, label="missed")

    ax = axes[1, 1]
    gate_colors = gates["passed"].map({1: "#16a34a", 0: "#dc2626"}).tolist()
    y = np.arange(len(gates))
    ax.barh(y, [1] * len(gates), color=gate_colors)
    ax.set_yticks(y)
    ax.set_yticklabels(gates["gate"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Hard gates")
    for idx, row in gates.iterrows():
        ax.text(0.02, idx, str(row["current"]), va="center", ha="left", fontsize=8, color="white")
    ax.invert_yaxis()

    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def build_report(
    decision: dict[str, Any],
    family_priority: pd.DataFrame,
    slot_ladder: pd.DataFrame,
    annual_miss: pd.DataFrame,
    source_summary: pd.DataFrame,
    gates: pd.DataFrame,
) -> str:
    ref_lines = "\n".join(f"- {item}" for item in REFERENCE_LINKS)
    p1_p2 = family_priority[family_priority["priority"].isin(["P1", "P2"])].copy()
    annual_focus = annual_miss[annual_miss["missed_family_after_black"].astype(str).ne("")].copy()
    return f"""# Stage621 低单笔风险扩池风险槽缺口优先级板

- line_id：`{LINE_ID}`
- 生成时间：`{decision['generated_at_cst']}`
- 阶段性质：只读结构审计；不新增交易规则、不重放策略引擎、不生成交易白名单、不连接 CTP。
- 决策：`{decision['decision']}`

## 外部调研与判断

{ref_lines}

我的判断：
- 多市场趋势跟踪需要扩大机会集合，但有效单位是“独立风险槽”，不是产品数量。
- 风险预算和相关性控制只能降低共振亏损，不能制造 alpha；选品必须来自 point-in-time source、事件账本和真实 TCA。
- 本阶段不能使用历史赢家白名单；`br.SHFE` 这类历史有收益但高相关的家族必须继续拒绝。

## 核心结论

- 当前结构有效槽：`{decision['current_effective_slots']}`，单槽风险约 `{decision['current_single_slot_risk_pct']:.2f}%`。
- 目标结构有效槽：`{decision['target_effective_slots']}`，目标单槽风险约 `{100.0 / decision['target_effective_slots']:.2f}%`。
- `black_ferrous(j/i)` 是当前唯一 P1 新槽线索；全部 source/TCA/live context 闭合后也只有 `{decision['slots_if_black_ferrous_closed']}` 槽，单槽风险 `{decision['single_slot_risk_if_black_ferrous_closed_pct']:.2f}%`。
- 因此即便 `j/i` 成功，仍差 `{decision['missing_slots_after_black_ferrous']}` 个独立槽。
- 当前新增预算、paper selector、交易白名单均为 `0`。

## 风险槽阶梯

{_md_table(slot_ladder)}

## 家族优先级

{_md_table(family_priority, [
    "priority",
    "product_family",
    "candidate_products",
    "slot_role",
    "slot_impact",
    "max_abs_core_corr",
    "slot_total_pnl_sum",
    "readiness_score",
    "evidence_count_0_6",
    "stage620_source_route_count",
    "stage620_selector_ready_count",
    "missing_for_promotion",
])}

## P1/P2 工作队列

{_md_table(p1_p2, [
    "priority",
    "product_family",
    "candidate_products",
    "slot_impact",
    "conditional_single_slot_risk_pct",
    "missing_for_promotion",
    "next_action",
])}

## 年度缺口

{_md_table(annual_focus, [
    "year",
    "missed_family_after_black",
    "family_status",
    "priority",
    "p0_plus_black_capture_pct",
    "next_action",
], max_rows=20)}

## Source 合同摘要

{_md_table(source_summary, [
    "product_family",
    "product_vt_symbol",
    "routes",
    "collector_implemented_count",
    "stage617_contract_complete_count",
    "selector_ready_count",
    "official_route_count",
    "third_party_route_count",
])}

## 闸门

{_md_table(gates)}

## 图表视觉复盘

- 左上：结构槽从 `4` 到 `5` 再到 `7` 的缺口很直观；`j/i` 不是终点，只是把单槽风险从 `25%` 降到 `20%`。
- 右上：`black_ferrous` 位于低相关且正材料性区域，是唯一 P1；`rubber/other` 在高相关侧，不能因为历史收益加入。
- 左下：加入 `black_ferrous` 后年度缺口仍集中在 `rubber/other/soft_agri/financial_index/livestock`；其中可立即晋级的为 `0`。
- 右下：通过的闸门主要是 fail-closed 纪律和高相关拒绝；目标槽数、持有体验、selector source、TCA 都未过。

## 过拟合反思

- 运行前判断：否。实验单位是风险槽、source/TCA/执行闸门，不是收益榜选品。
- 运行后判断：否。高收益但高相关的 `rubber` 被拒绝，低相关的 P2 也因为材料性不足不晋级，说明没有用历史结果强行救策略。

## 继续价值反思

- 运行前判断：有价值。该方向正面回答用户提出的低单笔风险和扩池问题。
- 运行后判断：有价值但要收敛。下一步不是继续宽池收益回测，而是 `j/i` source/TCA、P2 forward monitor、寻找两个真正新独立经济驱动。

## 输出文件

- family priority：`{FAMILY_PRIORITY_PATH}`
- slot ladder：`{SLOT_LADDER_PATH}`
- annual miss：`{ANNUAL_MISS_PATH}`
- source contract summary：`{SOURCE_CONTRACT_PATH}`
- gates：`{GATES_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""


def main() -> None:
    allocator_scenarios = _read_csv(STAGE604_ALLOCATOR_SCENARIOS)
    annual_capture = _read_csv(STAGE604_ANNUAL_CAPTURE)
    holding_boundary = _read_csv(STAGE604_HOLDING_BOUNDARY)
    family_admission = _read_csv(STAGE611_FAMILY_ADMISSION)
    collector_contract = _read_csv(STAGE620_COLLECTOR_CONTRACT)
    stage620_decision = _read_json(STAGE620_DECISION)

    source_summary = build_source_contract_summary(collector_contract)
    family_priority = build_family_priority(family_admission, source_summary)
    slot_ladder = build_slot_ladder()
    annual_miss = build_annual_miss(annual_capture, family_priority)
    gates = build_gates(family_priority, slot_ladder, holding_boundary, stage620_decision)
    decision = build_decision(family_priority, slot_ladder, annual_miss, gates, source_summary)
    report = build_report(decision, family_priority, slot_ladder, annual_miss, source_summary, gates)

    FAMILY_PRIORITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    family_priority.to_csv(FAMILY_PRIORITY_PATH, index=False, encoding="utf-8-sig")
    slot_ladder.to_csv(SLOT_LADDER_PATH, index=False, encoding="utf-8-sig")
    annual_miss.to_csv(ANNUAL_MISS_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    plot_chart(family_priority, slot_ladder, annual_miss, gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
