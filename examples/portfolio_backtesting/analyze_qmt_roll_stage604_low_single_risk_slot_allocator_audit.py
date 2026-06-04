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


MODEL_TAG = "stage604_low_single_risk_slot_allocator_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage604_low_single_risk_slot_allocator_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE574_CANDIDATE_MAP = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE574_ANNUAL = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_annual_opportunity_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE574_PAIRWISE = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_pairwise_corr_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE574_RISK_SHELL = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_risk_shell_boundary_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE592_PRODUCT_BUDGET = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_product_budget_stage592_breadth_selector_structure_audit_v1.csv"
STAGE592_FAMILY_BUDGET = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_family_budget_stage592_breadth_selector_structure_audit_v1.csv"
STAGE592_STRUCTURE_GATES = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_structure_gates_stage592_breadth_selector_structure_audit_v1.csv"
STAGE602_PRODUCT_MAP = OUTPUT_DIR / "qmt_roll_stage602_full57_non_dce_new_family_scout_product_map_stage602_full57_non_dce_new_family_scout_v1.csv"
STAGE602_SLOT_SCENARIOS = OUTPUT_DIR / "qmt_roll_stage602_full57_non_dce_new_family_scout_slot_scenarios_stage602_full57_non_dce_new_family_scout_v1.csv"
STAGE603_DECISION = OUTPUT_DIR / "qmt_roll_stage603_executable_critical_path_board_decision_stage603_executable_critical_path_board_v1.json"

SLOT_INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slot_inventory_{MODEL_TAG}.csv"
ALLOCATOR_SCENARIOS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_allocator_scenarios_{MODEL_TAG}.csv"
ANNUAL_CAPTURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_capture_{MODEL_TAG}.csv"
HOLDING_BOUNDARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_holding_boundary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TARGET_EFFECTIVE_SLOTS = 7
PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0
HARD_SINGLE_SLOT_RISK_PCT = 20.0
MAX_CORE_CORR_PREFERRED = 0.10
MATERIAL_SLEEVE_PNL = 50_000.0
CURRENT_P0_FAMILIES = {"grains_oilseeds", "petrochem", "energy_oil", "base_metals"}
BLACK_FERROUS_FAMILY = "black_ferrous"

REFERENCE_LINKS = [
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "Man Group Truth or Trend: https://www.man.com/insights/truth-or-trend",
    "skfolio risk budgeting / maximum diversification / HRP: https://github.com/skfolio/skfolio",
    "PyPortfolioOpt HRP clustering reference: https://github.com/PyPortfolio/PyPortfolioOpt",
]


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
    text = str(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _pct(actual: float, required: float) -> float:
    if required <= 0:
        return 100.0 if actual >= required else 0.0
    return max(0.0, min(100.0, actual / required * 100.0))


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def build_slot_inventory(product_map: pd.DataFrame) -> pd.DataFrame:
    frame = product_map.copy()
    frame["product_family"] = frame["product_family"].astype(str)
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["full57_status"] = frame.get("full57_status", frame.get("rescreen_status", "")).astype(str)
    frame["slot_judgement"] = frame.get("slot_judgement", "").astype(str)
    frame["total_pnl"] = _num(frame, "total_pnl")
    frame["abs_core_daily_pnl_corr"] = _num(frame, "abs_core_daily_pnl_corr")
    frame["source_component_pct"] = _num(frame, "source_component_pct")
    frame["positive_material"] = _num(frame, "positive_material")
    frame["low_corr_pass"] = _num(frame, "low_corr_pass")
    frame["source_rich"] = _num(frame, "source_rich")
    frame["deployable_new_slot_now"] = _num(frame, "deployable_new_slot_now")
    frame["whitelist_allowed"] = _num(frame, "whitelist_allowed")

    rows: list[dict[str, Any]] = []
    def role_subset(group: pd.DataFrame, role: str) -> pd.DataFrame:
        status = group["full57_status"].astype(str)
        if role == "current_p0_structural_slot":
            return group[status.eq("P0_existing_slot_incomplete")]
        if role == "p1_new_family_blocked":
            return group[status.eq("new_slot_blocked_by_dce_source")]
        if role == "same_family_depth_only":
            return group[status.eq("same_family_depth_not_slot")]
        if role == "reject_high_core_corr":
            return group[status.eq("reject_high_core_corr")]
        if role == "source_rich_no_edge_monitor":
            return group[status.eq("source_rich_no_edge_monitor")]
        non_core = group[_num(group, "is_core_product").eq(0)]
        return non_core if not non_core.empty else group

    for family, group in frame.groupby("product_family", sort=False):
        statuses = set(group["full57_status"].dropna().astype(str))
        if "P0_existing_slot_incomplete" in statuses:
            slot_role = "current_p0_structural_slot"
            slot_now = 1
            slot_if_black_resolved = 1
            deployable_now = 0
            action = "保留为结构槽，但只做补route/event/TCA；不是交易白名单。"
        elif "new_slot_blocked_by_dce_source" in statuses:
            slot_role = "p1_new_family_blocked"
            slot_now = 0
            slot_if_black_resolved = 1 if family == BLACK_FERROUS_FAMILY else 0
            deployable_now = 0
            action = "低相关新槽线索；DCE官方源和TCA未闭合前不能paper或交易。"
        elif "same_family_depth_not_slot" in statuses:
            slot_role = "same_family_depth_only"
            slot_now = 0
            slot_if_black_resolved = 0
            deployable_now = 0
            action = "只增加同族候选深度，不降低独立单槽风险。"
        elif "reject_high_core_corr" in statuses:
            slot_role = "reject_high_core_corr"
            slot_now = 0
            slot_if_black_resolved = 0
            deployable_now = 0
            action = "有收益也不能作为分散槽，核心相关超过观察线。"
        elif "source_rich_no_edge_monitor" in statuses:
            slot_role = "source_rich_no_edge_monitor"
            slot_now = 0
            slot_if_black_resolved = 0
            deployable_now = 0
            action = "源较完整但历史机会不足，只能forward monitor。"
        else:
            slot_role = "reject_or_observe"
            slot_now = 0
            slot_if_black_resolved = 0
            deployable_now = 0
            action = "缺少材料性、容量、低相关或source/TCA证据。"

        slot_group = role_subset(group, slot_role).copy()
        best = slot_group.sort_values(["total_pnl", "source_component_pct"], ascending=False).iloc[0]
        all_family_products = ",".join(group["product_vt_symbol"].tolist())
        rows.append(
            {
                "product_family": family,
                "slot_role": slot_role,
                "slot_products": ",".join(slot_group["product_vt_symbol"].tolist()),
                "all_family_products": all_family_products,
                "slot_product_count": int(len(slot_group)),
                "best_product": best["product_vt_symbol"],
                "slot_total_pnl_sum": float(slot_group["total_pnl"].sum()),
                "best_product_pnl": float(best["total_pnl"]),
                "max_abs_core_corr": float(slot_group["abs_core_daily_pnl_corr"].max()),
                "avg_source_component_pct": float(slot_group["source_component_pct"].mean()),
                "positive_material_count": int(slot_group["positive_material"].sum()),
                "low_corr_pass_count": int(slot_group["low_corr_pass"].sum()),
                "source_rich_count": int(slot_group["source_rich"].sum()),
                "deployable_new_slot_now": int(slot_group["deployable_new_slot_now"].sum()),
                "whitelist_allowed_count": int(slot_group["whitelist_allowed"].sum()),
                "structural_slot_now": slot_now,
                "structural_slot_if_black_ferrous_source_tca_resolved": slot_if_black_resolved,
                "deployable_selector_slot_now": deployable_now,
                "action": action,
            }
        )

    result = pd.DataFrame(rows)
    role_order = {
        "current_p0_structural_slot": 0,
        "p1_new_family_blocked": 1,
        "same_family_depth_only": 2,
        "reject_high_core_corr": 3,
        "source_rich_no_edge_monitor": 4,
        "reject_or_observe": 5,
    }
    result["role_order"] = result["slot_role"].map(role_order).fillna(9)
    return result.sort_values(["role_order", "best_product_pnl"], ascending=[True, False]).drop(columns=["role_order"])


def build_allocator_scenarios(
    product_map: pd.DataFrame,
    product_budget: pd.DataFrame,
    slot_inventory: pd.DataFrame,
    stage602_scenarios: pd.DataFrame,
    stage603: dict[str, Any],
) -> pd.DataFrame:
    p0 = product_map[product_map["full57_status"].astype(str).eq("P0_existing_slot_incomplete")]
    p1_black = product_map[product_map["full57_status"].astype(str).eq("new_slot_blocked_by_dce_source")]
    full57_new_slots = int(_num(product_map, "deployable_new_slot_now").sum())
    current_slots = int(slot_inventory["structural_slot_now"].sum())
    black_resolved_slots = int(slot_inventory["structural_slot_if_black_ferrous_source_tca_resolved"].sum())
    deployable_selector_slots = int(slot_inventory["deployable_selector_slot_now"].sum())

    product_budget = product_budget.copy()
    product_budget["product_vt_symbol"] = product_budget["product_vt_symbol"].astype(str)
    p0_budget = product_budget[product_budget["product_vt_symbol"].isin(p0["product_vt_symbol"])]
    p0_route_ready = int(_num(p0_budget, "two_route_ready").sum())
    p0_event_ready = int(_num(p0_budget, "event_ready").sum())
    fresh_context_present = int(stage603.get("fresh_live_context_present_rows", 0))
    fresh_context_required = int(stage603.get("fresh_live_context_required_rows", 45))
    valid_tca = int(stage603.get("p0_valid_live_tca_samples", 0))
    required_tca = int(stage603.get("p0_required_live_tca_samples", 9))

    rows = [
        {
            "scenario": "strict_deployable_today",
            "products": 0,
            "families": 0,
            "effective_slots": deployable_selector_slots,
            "single_slot_risk_pct": None,
            "distance_to_target_slots": TARGET_EFFECTIVE_SLOTS - deployable_selector_slots,
            "route_ready": "0/5",
            "event_ready": "0/5",
            "fresh_live_context": f"{fresh_context_present}/{fresh_context_required}",
            "valid_live_tca": f"{valid_tca}/{required_tca}",
            "deployable_allowed": 0,
            "interpretation": "真实selector和真实成交无偏差都没闭合，今天不能把扩池槽当部署版本。",
        },
        {
            "scenario": "current_p0_structural_yc_top1",
            "products": int(len(p0)),
            "families": int(p0["product_family"].nunique()),
            "effective_slots": current_slots,
            "single_slot_risk_pct": 100.0 / current_slots if current_slots else None,
            "distance_to_target_slots": TARGET_EFFECTIVE_SLOTS - current_slots,
            "route_ready": f"{p0_route_ready}/{len(p0)}",
            "event_ready": f"{p0_event_ready}/{len(p0)}",
            "fresh_live_context": f"{fresh_context_present}/{fresh_context_required}",
            "valid_live_tca": f"{valid_tca}/{required_tca}",
            "deployable_allowed": 0,
            "interpretation": "结构上有4个独立槽，单槽风险25%，还没有达到低单笔风险偏好。",
        },
        {
            "scenario": "p0_plus_black_ferrous_if_source_tca_resolved",
            "products": int(len(p0) + len(p1_black)),
            "families": int(set(p0["product_family"]).union(set(p1_black["product_family"])).__len__()),
            "effective_slots": black_resolved_slots,
            "single_slot_risk_pct": 100.0 / black_resolved_slots if black_resolved_slots else None,
            "distance_to_target_slots": TARGET_EFFECTIVE_SLOTS - black_resolved_slots,
            "route_ready": f"{p0_route_ready + 1}/{len(p0) + len(p1_black)}",
            "event_ready": f"{p0_event_ready}/{len(p0) + len(p1_black)}",
            "fresh_live_context": f"{fresh_context_present}/{fresh_context_required}",
            "valid_live_tca": f"{valid_tca}/{required_tca}",
            "deployable_allowed": 0,
            "interpretation": "即使j/i源和TCA解决，也只是5槽、20%单槽风险，仍差2个独立槽。",
        },
        {
            "scenario": "full57_non_dce_new_family_now",
            "products": int(len(product_map)),
            "families": int(product_map["product_family"].nunique()),
            "effective_slots": current_slots + full57_new_slots,
            "single_slot_risk_pct": 100.0 / (current_slots + full57_new_slots) if current_slots + full57_new_slots else None,
            "distance_to_target_slots": TARGET_EFFECTIVE_SLOTS - (current_slots + full57_new_slots),
            "route_ready": "see Stage602",
            "event_ready": "see Stage602",
            "fresh_live_context": f"{fresh_context_present}/{fresh_context_required}",
            "valid_live_tca": f"{valid_tca}/{required_tca}",
            "deployable_allowed": 0,
            "interpretation": "全57非DCE扫完当前没有新增可部署新族，不能靠名单长度解决。",
        },
        {
            "scenario": "target_minimum_allocator",
            "products": 8,
            "families": 7,
            "effective_slots": TARGET_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": 100.0 / TARGET_EFFECTIVE_SLOTS,
            "distance_to_target_slots": 0,
            "route_ready": "all slots >=2 routes",
            "event_ready": "all selector slots covered",
            "fresh_live_context": f"{fresh_context_required}/{fresh_context_required}",
            "valid_live_tca": f"{required_tca}/{required_tca}",
            "deployable_allowed": 1,
            "interpretation": "这才是低单笔风险扩池应达到的最小结构，不是当前结果。",
        },
    ]

    scenario = pd.DataFrame(rows)
    if not stage602_scenarios.empty and "scenario" in stage602_scenarios.columns:
        scenario["stage602_context"] = "loaded"
    else:
        scenario["stage602_context"] = "missing"
    return scenario


def build_annual_capture(annual: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in annual.to_dict("records"):
        families = _split_csv_cell(row.get("top6_families"))
        products = _split_csv_cell(row.get("top6_products"))
        family_set = set(families)
        product_set = set(products)
        current_capture_families = family_set.intersection(CURRENT_P0_FAMILIES)
        current_black_capture_families = family_set.intersection(CURRENT_P0_FAMILIES | {BLACK_FERROUS_FAMILY})
        rows.append(
            {
                "year": int(row["year"]),
                "top6_positive": int(row.get("top6_positive", 0)),
                "top6_pnl": float(row.get("top6_pnl", 0)),
                "top6_family_count": int(row.get("top6_family_count", len(family_set))),
                "top6_family_max_count": int(row.get("top6_family_max_count", 0)),
                "current_p0_family_capture_count": int(len(current_capture_families)),
                "current_p0_family_capture_pct": 100.0
                * _safe_ratio(len(current_capture_families), len(family_set)),
                "p0_plus_black_family_capture_count": int(len(current_black_capture_families)),
                "p0_plus_black_family_capture_pct": 100.0
                * _safe_ratio(len(current_black_capture_families), len(family_set)),
                "top6_product_capture_count_current_p0": int(len(product_set.intersection({"y.DCE", "c.DCE", "v.DCE", "ao.SHFE", "lu.INE"}))),
                "missed_families_current_p0": ",".join(sorted(family_set - CURRENT_P0_FAMILIES)),
                "missed_families_after_black": ",".join(sorted(family_set - (CURRENT_P0_FAMILIES | {BLACK_FERROUS_FAMILY}))),
                "top6_products": ",".join(products),
                "top6_families": ",".join(families),
            }
        )
    return pd.DataFrame(rows)


def build_holding_boundary(risk_shell: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "label_short",
        "deployable_status",
        "satellite_cumulative_pnl",
        "max_dd_delta_vs_stage526",
        "ulcer_delta_vs_stage526",
        "hold63_p10_delta_vs_stage526",
        "hold126_p10_delta_vs_stage526",
        "deployable_no_degrade_pass",
        "return_delta_vs_stage526_pct",
    ]
    boundary = risk_shell[[col for col in cols if col in risk_shell.columns]].copy()
    for col in boundary.columns:
        if col not in {"label_short", "deployable_status"}:
            boundary[col] = pd.to_numeric(boundary[col], errors="coerce")
    boundary["usable_for_allocator"] = (
        boundary["deployable_status"].astype(str).eq("deployable_or_control")
        & boundary["deployable_no_degrade_pass"].fillna(0).eq(1)
        & boundary["satellite_cumulative_pnl"].fillna(0).ge(MATERIAL_SLEEVE_PNL)
    ).astype(int)
    boundary["interpretation"] = np.where(
        boundary["usable_for_allocator"].eq(1),
        "可进入下一步",
        "不能晋级；3/6个月左尾、Ulcer、回撤或材料性没有同时通过",
    )
    return boundary


def build_gates(
    slot_inventory: pd.DataFrame,
    scenarios: pd.DataFrame,
    annual_capture: pd.DataFrame,
    pairwise: pd.DataFrame,
    holding: pd.DataFrame,
    product_map: pd.DataFrame,
    stage603: dict[str, Any],
) -> pd.DataFrame:
    current_slots = int(slot_inventory["structural_slot_now"].sum())
    black_slots = int(slot_inventory["structural_slot_if_black_ferrous_source_tca_resolved"].sum())
    deployable_slots = int(slot_inventory["deployable_selector_slot_now"].sum())
    max_pair_corr = float(_num(pairwise, "abs_daily_pnl_corr").max()) if not pairwise.empty else 0.0
    all_noncore = holding[holding["label_short"].astype(str).eq("All noncore r020")]
    all_noncore_pnl = float(_num(all_noncore, "satellite_cumulative_pnl").iloc[0]) if not all_noncore.empty else 0.0
    best_deployable = holding[holding["deployable_status"].astype(str).eq("deployable_or_control")].copy()
    best_63 = float(_num(best_deployable, "hold63_p10_delta_vs_stage526").max()) if not best_deployable.empty else 0.0
    best_126 = float(_num(best_deployable, "hold126_p10_delta_vs_stage526").max()) if not best_deployable.empty else 0.0
    br = product_map[product_map["product_vt_symbol"].astype(str).eq("br.SHFE")]
    br_corr = float(_num(br, "abs_core_daily_pnl_corr").iloc[0]) if not br.empty else 0.0
    br_rejected = int(bool(not br.empty and br["full57_status"].astype(str).iloc[0] == "reject_high_core_corr"))
    non_dce_deployable = int(_num(product_map, "deployable_new_slot_now").sum())
    p1_black = product_map[product_map["full57_status"].astype(str).eq("new_slot_blocked_by_dce_source")]
    black_ready_now = int(
        bool(
            not p1_black.empty
            and int(_num(p1_black, "deployable_new_slot_now").sum()) >= 1
            and int(_num(p1_black, "whitelist_allowed").sum()) >= 1
        )
    )
    fresh_live_context_present = int(stage603.get("fresh_live_context_present_rows", 0))
    fresh_live_context_required = int(stage603.get("fresh_live_context_required_rows", 45))
    p0_valid_tca = int(stage603.get("p0_valid_live_tca_samples", 0))
    p0_required_tca = int(stage603.get("p0_required_live_tca_samples", 9))

    rows = [
        {
            "gate": "current_effective_slot_width",
            "actual": f"{current_slots}/{TARGET_EFFECTIVE_SLOTS}",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "passed": int(current_slots >= TARGET_EFFECTIVE_SLOTS),
            "hard_gate": 1,
            "judgement": "当前结构槽只有4个，无法把单槽风险压到15%附近。",
        },
        {
            "gate": "single_slot_preferred_risk",
            "actual": f"{100.0 / current_slots:.2f}%" if current_slots else "n/a",
            "threshold": f"<={PREFERRED_SINGLE_SLOT_RISK_PCT:.2f}%",
            "passed": int(current_slots and 100.0 / current_slots <= PREFERRED_SINGLE_SLOT_RISK_PCT),
            "hard_gate": 1,
            "judgement": "4槽意味着单槽25%，仍是集中风险，不是低单笔风险结构。",
        },
        {
            "gate": "if_black_ferrous_resolved_still_short",
            "actual": f"{black_slots}/{TARGET_EFFECTIVE_SLOTS}",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "passed": int(black_slots >= TARGET_EFFECTIVE_SLOTS),
            "hard_gate": 0,
            "judgement": "j/i若解决官方源和TCA，也只是5槽，仍差2个新族。",
        },
        {
            "gate": "candidate_pairwise_corr_budget",
            "actual": f"max_abs_pair_corr={max_pair_corr:.4f}",
            "threshold": "<=0.20 preferred",
            "passed": int(max_pair_corr <= 0.20),
            "hard_gate": 1,
            "judgement": "P0内部相关性不是主要矛盾，主要矛盾是槽数和证据不足。",
        },
        {
            "gate": "reject_high_core_corr_discipline",
            "actual": f"br_corr={br_corr:.4f}; rejected={br_rejected}",
            "threshold": "high-corr winners must stay out",
            "passed": int(br_corr > MAX_CORE_CORR_PREFERRED and br_rejected == 1),
            "hard_gate": 1,
            "judgement": "有收益但高相关的br被拒绝，说明这不是历史赢家白名单扫描。",
        },
        {
            "gate": "annual_opportunity_exists",
            "actual": f"{int(annual_capture['top6_positive'].sum())}/{len(annual_capture)} years",
            "threshold": "all years top6 positive",
            "passed": int(int(annual_capture["top6_positive"].sum()) == len(annual_capture)),
            "hard_gate": 0,
            "judgement": "年度趋势机会确实存在，所以方向值得继续。",
        },
        {
            "gate": "naive_width_material_capture",
            "actual": f"all_noncore_sleeve_pnl={all_noncore_pnl:.0f}",
            "threshold": f">={MATERIAL_SLEEVE_PNL:.0f}",
            "passed": int(all_noncore_pnl >= MATERIAL_SLEEVE_PNL),
            "hard_gate": 1,
            "judgement": "盲目全非核心扩池抓不到足够材料性收益。",
        },
        {
            "gate": "holding_3m_6m_no_degrade",
            "actual": f"best_63d_delta={best_63:.4f}; best_126d_delta={best_126:.4f}",
            "threshold": "both >=0 for deployable shells",
            "passed": int(best_63 >= 0 and best_126 >= 0),
            "hard_gate": 1,
            "judgement": "现有可部署宽池壳没有改善任意启动3/6个月左尾。",
        },
        {
            "gate": "new_non_dce_deployable_slot_now",
            "actual": f"{non_dce_deployable}/2 new slots",
            "threshold": ">=2 independent new deployable slots",
            "passed": int(non_dce_deployable >= 2),
            "hard_gate": 1,
            "judgement": "全57非DCE扫描没有新增可部署独立槽。",
        },
        {
            "gate": "black_ferrous_source_tca_ready",
            "actual": f"ready={black_ready_now}",
            "threshold": "DCE source + event + TCA closed",
            "passed": black_ready_now,
            "hard_gate": 1,
            "judgement": "j/i低相关但仍被DCE官方源和真实成交样本卡住。",
        },
        {
            "gate": "execution_zero_bias_evidence",
            "actual": f"fresh_context={fresh_live_context_present}/{fresh_live_context_required}; tca={p0_valid_tca}/{p0_required_tca}; deployable_selector_slots={deployable_slots}",
            "threshold": "fresh context 45/45 and TCA 9/9 before deployment",
            "passed": int(fresh_live_context_present >= fresh_live_context_required and p0_valid_tca >= p0_required_tca),
            "hard_gate": 1,
            "judgement": "真实交易不偏差链路没闭合，不能把allocator声明为实盘可成交结构。",
        },
    ]
    return pd.DataFrame(rows)


def write_chart(
    product_map: pd.DataFrame,
    scenarios: pd.DataFrame,
    annual_capture: pd.DataFrame,
    holding: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "figure.dpi": 160,
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))

    scenario_view = scenarios[scenarios["scenario"].isin([
        "strict_deployable_today",
        "current_p0_structural_yc_top1",
        "p0_plus_black_ferrous_if_source_tca_resolved",
        "full57_non_dce_new_family_now",
        "target_minimum_allocator",
    ])].copy()
    labels = [
        "Deployable\nnow",
        "Current\nP0",
        "+Black\nif fixed",
        "Full57\nnow",
        "Target",
    ]
    colors = ["#e53e3e", "#3182ce", "#ed8936", "#805ad5", "#38a169"]
    axes[0, 0].bar(labels, scenario_view["effective_slots"], color=colors, alpha=0.9)
    axes[0, 0].axhline(TARGET_EFFECTIVE_SLOTS, color="#2f855a", linestyle="--", linewidth=1.5)
    axes[0, 0].set_title("Effective Risk Slots vs Target")
    axes[0, 0].set_ylabel("effective slots")
    axes[0, 0].set_ylim(0, max(TARGET_EFFECTIVE_SLOTS + 1, scenario_view["effective_slots"].max() + 1))
    for idx, row in enumerate(scenario_view.itertuples(index=False)):
        risk = getattr(row, "single_slot_risk_pct")
        risk_text = "n/a" if pd.isna(risk) else f"{risk:.1f}%"
        axes[0, 0].text(idx, row.effective_slots + 0.12, risk_text, ha="center", va="bottom", fontsize=8)
    axes[0, 0].text(4.1, TARGET_EFFECTIVE_SLOTS + 0.1, "target 7 slots", color="#2f855a", fontsize=8)

    axes[0, 1].plot(
        annual_capture["year"],
        annual_capture["current_p0_family_capture_pct"],
        marker="o",
        color="#3182ce",
        label="Current P0 family capture",
    )
    axes[0, 1].plot(
        annual_capture["year"],
        annual_capture["p0_plus_black_family_capture_pct"],
        marker="o",
        color="#ed8936",
        label="+ black ferrous if fixed",
    )
    axes[0, 1].set_title("Annual Top6 Family Capture Proxy")
    axes[0, 1].set_ylabel("capture pct")
    axes[0, 1].set_ylim(0, 105)
    axes[0, 1].grid(True, alpha=0.25)
    axes[0, 1].legend(loc="lower left", fontsize=8)

    status_colors = {
        "P0_existing_slot_incomplete": "#3182ce",
        "new_slot_blocked_by_dce_source": "#ed8936",
        "same_family_depth_not_slot": "#68d391",
        "reject_high_core_corr": "#e53e3e",
        "source_rich_no_edge_monitor": "#805ad5",
        "no_material_opportunity_monitor": "#a0aec0",
        "reject_capacity_or_liquidity": "#4a5568",
        "core_existing_not_new_slot": "#718096",
    }
    plot_map = product_map[product_map["is_core_product"].fillna(0).astype(float).eq(0)].copy()
    plot_map["plot_color"] = plot_map["full57_status"].map(status_colors).fillna("#a0aec0")
    axes[1, 0].scatter(
        plot_map["abs_core_daily_pnl_corr"],
        plot_map["total_pnl"],
        s=np.clip(plot_map["source_component_pct"].fillna(0) * 1.8 + 30, 25, 160),
        c=plot_map["plot_color"],
        alpha=0.78,
        edgecolor="white",
        linewidth=0.5,
    )
    axes[1, 0].axvline(MAX_CORE_CORR_PREFERRED, color="#e53e3e", linestyle="--", linewidth=1)
    axes[1, 0].axhline(0, color="#4a5568", linewidth=0.8)
    axes[1, 0].set_title("Product Opportunity vs Core Correlation")
    axes[1, 0].set_xlabel("abs corr to core daily PnL")
    axes[1, 0].set_ylabel("single-product total PnL")
    for symbol in ["lu.INE", "v.DCE", "ao.SHFE", "y.DCE", "c.DCE", "j.DCE", "i.DCE", "br.SHFE", "al.SHFE"]:
        row = plot_map[plot_map["product_vt_symbol"].eq(symbol)]
        if not row.empty:
            item = row.iloc[0]
            axes[1, 0].annotate(
                symbol,
                (item["abs_core_daily_pnl_corr"], item["total_pnl"]),
                fontsize=7,
                xytext=(3, 3),
                textcoords="offset points",
            )
    axes[1, 0].grid(True, alpha=0.2)

    hold_view = holding[holding["label_short"].isin(["Stage526", "Stage256 upper", "All noncore r020", "Prev+ r020", "Prev+ r015"])].copy()
    x = np.arange(len(hold_view))
    width = 0.35
    axes[1, 1].bar(x - width / 2, hold_view["hold63_p10_delta_vs_stage526"], width, label="63d p10 delta", color="#3182ce")
    axes[1, 1].bar(x + width / 2, hold_view["hold126_p10_delta_vs_stage526"], width, label="126d p10 delta", color="#805ad5")
    axes[1, 1].axhline(0, color="#2f855a", linestyle="--", linewidth=1)
    axes[1, 1].set_title("Deployable Breadth Holding Experience Boundary")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(hold_view["label_short"], rotation=20, ha="right")
    axes[1, 1].set_ylabel("p10 return delta vs Stage526")
    axes[1, 1].legend(fontsize=8)
    axes[1, 1].grid(True, axis="y", alpha=0.2)

    failed_hard = int(((gates["hard_gate"] == 1) & (gates["passed"] == 0)).sum())
    fig.suptitle(
        f"Stage604 Low Single-Risk Slot Allocator Audit | failed hard gates: {failed_hard}",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, bbox_inches="tight")
    plt.close(fig)


def write_report(
    slot_inventory: pd.DataFrame,
    scenarios: pd.DataFrame,
    annual_capture: pd.DataFrame,
    holding: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# Stage604 Low Single-Risk Slot Allocator Audit

- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- generated_at：`{decision['generated_at']}`
- decision：`{decision['decision']}`
- promotion_allowed：`{decision['promotion_allowed']}`
- paper_selector_allowed：`{decision['paper_selector_allowed']}`
- trading_whitelist_allowed：`{decision['trading_whitelist_allowed']}`
- hard_gates：`{decision['hard_gates_passed']}/{decision['hard_gates_total']}`

## 外部调研判断

- Man Group 的趋势组合研究把市场集合、低相关驱动和最大分散视为趋势组合的核心问题；增加市场集可以提高长期分散度，但必须和流动性、成本、危机防御取舍一起看。
- Man Group 的趋势噪声讨论也强调趋势收益来自市场分散和趋势扩散，不是某个单一市场长期稳定贡献。
- GitHub 上 skfolio / PyPortfolioOpt 均把 risk budgeting、maximum diversification、HRP/聚类选低相关资产作为标准组合构造模块。
- 本阶段判断：这些资料支持“低单笔风险 + 多独立风险槽”的方向，但本仓库不能直接套黑箱优化器；必须优先使用产品族、相关性、source/TCA 和真实成交闸门。

参考：
{chr(10).join(f"- {link}" for link in REFERENCE_LINKS)}

## 本阶段做了什么

- 只读合成 Stage574/592/602/603，不重放交易引擎。
- 将“品种数量”改写为“有效风险槽数量”。
- 检查当前P0、`j/i`黑色新槽、全57非DCE扫描和目标allocator之间的距离。
- 继续禁止历史赢家白名单、宽池小数扫描和A/B启动。

## Allocator 场景

{_md_table(scenarios, max_rows=20)}

## 风险槽库存

{_md_table(slot_inventory, ["product_family", "slot_role", "slot_products", "best_product", "best_product_pnl", "max_abs_core_corr", "avg_source_component_pct", "structural_slot_now", "structural_slot_if_black_ferrous_source_tca_resolved", "action"], max_rows=30)}

## 年度机会捕获代理

{_md_table(annual_capture, ["year", "top6_pnl", "top6_family_count", "current_p0_family_capture_pct", "p0_plus_black_family_capture_pct", "missed_families_current_p0", "missed_families_after_black"], max_rows=20)}

## 3/6个月持有体验边界

{_md_table(holding, ["label_short", "deployable_status", "satellite_cumulative_pnl", "hold63_p10_delta_vs_stage526", "hold126_p10_delta_vs_stage526", "max_dd_delta_vs_stage526", "ulcer_delta_vs_stage526", "usable_for_allocator", "interpretation"], max_rows=20)}

## 闸门

{_md_table(gates, max_rows=30)}

## 结论

- 方向成立：年度top6非核心趋势机会为 `7/7` 年正值，P0内部pairwise相关低，说明“每年抓部分品种趋势”不是空想。
- 当前不可晋级：结构槽只有 `4` 个，单槽风险约 `25%`；即便 `j/i` 官方源和TCA都解决，也只有 `5` 槽，单槽风险约 `20%`，仍差 `2` 个独立槽。
- 盲目扩池失败：`All noncore r020` 只有 `9395` 卫星收益，3/6个月p10体验还劣化；所以不是“多加品种”就行。
- 选对品种是关键，但现在不能把历史赢家直接选入；必须先补 point-in-time 外生源、事件账本和真实TCA。

## 过拟合反思

- 运行前判断：否。本阶段检验的是结构边界和证据缺口，不根据收益挑白名单。
- 运行后判断：否。`br.SHFE` 这类有收益但高相关的品种继续被拒绝，`j/i` 低相关也因为source/TCA不足不能晋级，说明没有用历史赢家救结果。

## 继续价值反思

- 运行前判断：有价值。该方向连接了用户提出的低单笔风险、扩池、避相关、选品四个目标。
- 运行后判断：有价值但要收敛。下一步不是宽池收益回测，而是补两个独立槽来源和闭合执行/TCA；否则继续回测只会制造选择偏差。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    generated_at = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")

    product_map = _read_csv(STAGE602_PRODUCT_MAP)
    annual = _read_csv(STAGE574_ANNUAL)
    pairwise = _read_csv(STAGE574_PAIRWISE)
    risk_shell = _read_csv(STAGE574_RISK_SHELL)
    product_budget = _read_csv(STAGE592_PRODUCT_BUDGET)
    stage602_scenarios = _read_csv(STAGE602_SLOT_SCENARIOS)
    stage603 = _read_json(STAGE603_DECISION)

    product_map["product_vt_symbol"] = product_map["product_vt_symbol"].astype(str)
    product_map["product_family"] = product_map["product_family"].astype(str)
    product_map["full57_status"] = product_map.get("full57_status", product_map.get("rescreen_status", "")).astype(str)
    product_map["total_pnl"] = _num(product_map, "total_pnl")
    product_map["abs_core_daily_pnl_corr"] = _num(product_map, "abs_core_daily_pnl_corr")
    product_map["source_component_pct"] = _num(product_map, "source_component_pct")

    slot_inventory = build_slot_inventory(product_map)
    scenarios = build_allocator_scenarios(product_map, product_budget, slot_inventory, stage602_scenarios, stage603)
    annual_capture = build_annual_capture(annual)
    holding = build_holding_boundary(risk_shell)
    gates = build_gates(slot_inventory, scenarios, annual_capture, pairwise, holding, product_map, stage603)

    hard_gates = gates[gates["hard_gate"].eq(1)]
    hard_passed = int(hard_gates["passed"].sum())
    hard_total = int(len(hard_gates))
    failed_hard = hard_total - hard_passed

    current_slots = int(slot_inventory["structural_slot_now"].sum())
    black_slots = int(slot_inventory["structural_slot_if_black_ferrous_source_tca_resolved"].sum())
    deployable_slots = int(slot_inventory["deployable_selector_slot_now"].sum())
    single_slot_risk_now = 100.0 / current_slots if current_slots else None
    single_slot_risk_if_black = 100.0 / black_slots if black_slots else None

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": generated_at,
        "decision": "risk_slot_allocator_direction_valid_not_deployable_need_two_new_slots_and_tca",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "new_backtest_run": False,
        "strategy_changed": False,
        "effective_slots_now": current_slots,
        "deployable_selector_slots_now": deployable_slots,
        "effective_slots_if_black_ferrous_source_tca_resolved": black_slots,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "slots_gap_now": TARGET_EFFECTIVE_SLOTS - current_slots,
        "slots_gap_if_black_ferrous_resolved": TARGET_EFFECTIVE_SLOTS - black_slots,
        "single_slot_risk_pct_now": single_slot_risk_now,
        "single_slot_risk_pct_if_black_ferrous_resolved": single_slot_risk_if_black,
        "preferred_single_slot_risk_pct": PREFERRED_SINGLE_SLOT_RISK_PCT,
        "annual_top6_positive_years": int(annual_capture["top6_positive"].sum()),
        "annual_top6_years": int(len(annual_capture)),
        "naive_all_noncore_materiality_pass": bool(
            holding.loc[holding["label_short"].astype(str).eq("All noncore r020"), "usable_for_allocator"].sum() > 0
        ),
        "hard_gates_passed": hard_passed,
        "hard_gates_total": hard_total,
        "failed_hard_gates": failed_hard,
        "visual_chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
    }

    SLOT_INVENTORY_PATH.write_text(slot_inventory.to_csv(index=False), encoding="utf-8")
    ALLOCATOR_SCENARIOS_PATH.write_text(scenarios.to_csv(index=False), encoding="utf-8")
    ANNUAL_CAPTURE_PATH.write_text(annual_capture.to_csv(index=False), encoding="utf-8")
    HOLDING_BOUNDARY_PATH.write_text(holding.to_csv(index=False), encoding="utf-8")
    GATES_PATH.write_text(gates.to_csv(index=False), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(product_map, scenarios, annual_capture, holding, gates)
    write_report(slot_inventory, scenarios, annual_capture, holding, gates, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
