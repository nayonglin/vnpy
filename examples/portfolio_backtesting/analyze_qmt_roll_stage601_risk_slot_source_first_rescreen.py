from __future__ import annotations

from datetime import datetime, timezone
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


MODEL_TAG = "stage601_risk_slot_source_first_rescreen_v1"
OUTPUT_PREFIX = "qmt_roll_stage601_risk_slot_source_first_rescreen"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE574_CANDIDATE_MAP = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE597_PRODUCT_WORKLIST = OUTPUT_DIR / "qmt_roll_stage597_new_family_source_tca_worklist_product_worklist_stage597_new_family_source_tca_worklist_v1.csv"
STAGE597_GATES = OUTPUT_DIR / "qmt_roll_stage597_new_family_source_tca_worklist_gates_stage597_new_family_source_tca_worklist_v1.csv"
STAGE600_DECISION = OUTPUT_DIR / "qmt_roll_stage600_dce_412_browser_session_probe_decision_stage600_dce_412_browser_session_probe_v1.json"
STAGE600_GATES = OUTPUT_DIR / "qmt_roll_stage600_dce_412_browser_session_probe_gates_stage600_dce_412_browser_session_probe_v1.csv"
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / "qmt_roll_stage571_external_selector_source_priority_audit_source_priority_stage571_external_selector_source_priority_audit_v1.csv"

PRODUCT_RESCREEN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_rescreen_{MODEL_TAG}.csv"
FAMILY_RESCREEN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_rescreen_{MODEL_TAG}.csv"
SLOT_SCENARIO_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slot_scenarios_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_FAMILIES = {"grains_oilseeds", "petrochem", "energy_oil", "base_metals"}
P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 = 4
TARGET_EFFECTIVE_SLOTS = 7
TARGET_MAX_SLOT_RISK_PCT = 15.0
MAX_CORE_CORR_WATCH = 0.10
SOURCE_RICH_COMPONENT_PCT = 80.0
MATERIAL_FAMILY_PNL = 50_000.0

REFERENCE_LINKS = [
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "Optimal Allocation of Trend Following Strategies: https://arxiv.org/abs/1410.8409",
    "Diversifying Trends / CoTrend: https://www.sciencedirect.com/science/article/abs/pii/S245230622100109X",
    "skfolio HRP/Hierarchical clustering: https://skfolio.org/generated/skfolio.optimization.HierarchicalRiskParity.html",
    "PyPortfolioOpt HRP: https://pyportfolioopt.readthedocs.io/en/stable/OtherOptimizers.html",
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


def _load_product_rescreen() -> pd.DataFrame:
    candidate_map = _read_csv(STAGE574_CANDIDATE_MAP)
    worklist = _read_csv(STAGE597_PRODUCT_WORKLIST)

    source_cols = [
        "product_vt_symbol",
        "source_component_count",
        "source_component_pct",
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "capacity_pass_hint",
        "priority",
        "action",
        "reason",
        "tier",
    ]
    frame = candidate_map.merge(
        worklist[[column for column in source_cols if column in worklist.columns]],
        on="product_vt_symbol",
        how="left",
        suffixes=("", "_stage597"),
    )
    for column in [
        "total_pnl",
        "positive_year_rate_pct",
        "abs_core_daily_pnl_corr",
        "single_hard_volume_stress_event_rate_pct",
        "single_max_order_volume_to_day_volume_pct",
        "source_component_count",
        "source_component_pct",
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "capacity_pass_hint",
    ]:
        frame[column] = _num(frame, column)

    frame["tier"] = frame["tier"].fillna("Observe_only")
    frame["priority"] = frame["priority"].fillna("观察")
    frame["action"] = frame["action"].fillna("不进入当前扩池工作流")
    frame["reason"] = frame["reason"].fillna("未进入Stage597工作清单")
    frame["is_p0_family"] = frame["product_family"].astype(str).isin(P0_FAMILIES).astype(int)
    frame["is_new_family"] = (1 - frame["is_p0_family"]).astype(int)
    frame["low_core_corr_pass"] = frame["abs_core_daily_pnl_corr"].le(MAX_CORE_CORR_WATCH).astype(int)
    frame["source_rich"] = frame["source_component_pct"].ge(SOURCE_RICH_COMPONENT_PCT).astype(int)
    frame["positive_pnl"] = frame["total_pnl"].gt(0).astype(int)
    frame["material_hint"] = frame["total_pnl"].ge(10_000.0).astype(int)

    source_score = frame["source_component_pct"].clip(0, 100) / 100.0
    corr_score = (1.0 - frame["abs_core_daily_pnl_corr"].clip(0, 0.30) / 0.30).clip(0, 1)
    material_score = frame["total_pnl"].clip(lower=0, upper=MATERIAL_FAMILY_PNL) / MATERIAL_FAMILY_PNL
    year_score = frame["positive_year_rate_pct"].clip(0, 100) / 100.0
    capacity_score = frame["capacity_pass_hint"].clip(0, 1)
    new_family_score = frame["is_new_family"].clip(0, 1)
    frame["source_first_score"] = (
        25 * source_score
        + 25 * corr_score
        + 20 * capacity_score
        + 15 * material_score
        + 10 * year_score
        + 5 * new_family_score
    )

    statuses = []
    for _, row in frame.iterrows():
        tier = str(row["tier"])
        family = str(row["product_family"])
        if tier == "P0_forward_watch":
            statuses.append("P0_existing_slot_incomplete")
        elif tier == "P1_same_family_depth_only":
            statuses.append("same_family_depth_not_slot")
        elif family == "black_ferrous" and tier == "P1_new_family_candidate":
            statuses.append("new_slot_blocked_by_dce_source")
        elif tier == "Reject_core_corr_watch":
            statuses.append("reject_high_core_corr")
        elif int(row["source_rich"]) == 1 and int(row["low_core_corr_pass"]) == 1 and float(row["total_pnl"]) <= 0:
            statuses.append("source_rich_no_edge_monitor")
        elif tier == "Reject_no_material_opportunity":
            statuses.append("no_material_opportunity_monitor")
        elif tier == "Reject_capacity_or_liquidity":
            statuses.append("reject_capacity_or_liquidity")
        else:
            statuses.append("observe_only")
    frame["rescreen_status"] = statuses
    frame["whitelist_allowed"] = 0
    return frame.sort_values(["rescreen_status", "source_first_score"], ascending=[True, False])


def _build_family_rescreen(product_rescreen: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, group in product_rescreen.groupby("product_family", sort=False):
        positive = group[group["total_pnl"].gt(0)].copy()
        best = group.sort_values("source_first_score", ascending=False).iloc[0]
        statuses = set(group["rescreen_status"].astype(str))
        p0_count = int(group["rescreen_status"].eq("P0_existing_slot_incomplete").sum())
        same_depth_count = int(group["rescreen_status"].eq("same_family_depth_not_slot").sum())
        blocked_new_count = int(group["rescreen_status"].eq("new_slot_blocked_by_dce_source").sum())
        source_rich_no_edge_count = int(group["rescreen_status"].eq("source_rich_no_edge_monitor").sum())
        if p0_count:
            status = "P0_existing_slot_incomplete"
            judgement = "已有风险槽，重点是route/event/TCA补证，不增加槽数。"
        elif blocked_new_count:
            status = "P1_new_slot_blocked_by_dce_source"
            judgement = "低相关新族，但DCE官方源被412/400阻塞；未授权替代源前不能paper。"
        elif same_depth_count:
            status = "same_family_depth_not_slot"
            judgement = "能做同族替补或tie-break，但不降低独立单槽风险。"
        elif "reject_high_core_corr" in statuses and float(positive["total_pnl"].sum()) > 0:
            status = "reject_high_core_corr"
            judgement = "有正收益代表但核心相关过高，不能作为分散槽。"
        elif source_rich_no_edge_count:
            status = "source_rich_no_edge_monitor"
            judgement = "source较完整、相关低，但历史机会不足；只做低频forward monitor。"
        elif float(positive["total_pnl"].sum()) > 0:
            status = "positive_but_not_operational_slot"
            judgement = "有局部正收益但未同时通过材料性/容量/source/相关闸门。"
        else:
            status = "no_current_slot_value"
            judgement = "当前没有投入TCA或selector验证的价值。"
        rows.append(
            {
                "product_family": family,
                "family_status": status,
                "products": int(len(group)),
                "product_list": ",".join(group["product_vt_symbol"].astype(str).tolist()),
                "best_source_first_product": str(best["product_vt_symbol"]),
                "best_source_first_score": float(best["source_first_score"]),
                "positive_products": int(group["total_pnl"].gt(0).sum()),
                "family_positive_pnl_sum": float(positive["total_pnl"].sum()),
                "family_total_pnl_sum": float(group["total_pnl"].sum()),
                "family_max_abs_core_corr": float(group["abs_core_daily_pnl_corr"].max()),
                "source_rich_products": int(group["source_rich"].sum()),
                "live_state_products": int(group["any_live_external_state"].sum()),
                "p0_products": p0_count,
                "same_family_depth_products": same_depth_count,
                "blocked_new_slot_products": blocked_new_count,
                "deployable_new_slot_now": 0,
                "judgement": judgement,
            }
        )
    frame = pd.DataFrame(rows)
    order = {
        "P0_existing_slot_incomplete": 0,
        "P1_new_slot_blocked_by_dce_source": 1,
        "same_family_depth_not_slot": 2,
        "reject_high_core_corr": 3,
        "source_rich_no_edge_monitor": 4,
        "positive_but_not_operational_slot": 5,
        "no_current_slot_value": 6,
    }
    frame["_order"] = frame["family_status"].map(order).fillna(99)
    return frame.sort_values(["_order", "best_source_first_score"], ascending=[True, False]).drop(columns=["_order"])


def _build_slot_scenarios(family_rescreen: pd.DataFrame) -> pd.DataFrame:
    black_blocked = int(family_rescreen["family_status"].eq("P1_new_slot_blocked_by_dce_source").sum())
    scenarios = [
        {
            "scenario": "current_P0_effective_after_yc_top1",
            "effective_slots": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "single_slot_risk_pct": 100.0 / P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "allowed_now": 1,
            "comment": "P0只有4个有效独立槽，y/c同族同向只能算一个。",
        },
        {
            "scenario": "after_same_family_depth",
            "effective_slots": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "single_slot_risk_pct": 100.0 / P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "allowed_now": 1,
            "comment": "al/bu/TA/pg等只能提升同族深度，不增加独立槽。",
        },
        {
            "scenario": "after_dce_blocker_current_state",
            "effective_slots": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "single_slot_risk_pct": 100.0 / P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "allowed_now": 1,
            "comment": "Stage599/600后black_ferrous仍不能算可交易槽。",
        },
        {
            "scenario": "if_black_ferrous_authorized_source_resolved",
            "effective_slots": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 + min(black_blocked, 1),
            "single_slot_risk_pct": 100.0 / (P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 + min(black_blocked, 1)),
            "allowed_now": 0,
            "comment": "只有找到可授权/稳定替代DCE源并补TCA后，j/i才可能成为第5槽。",
        },
        {
            "scenario": "preferred_target",
            "effective_slots": TARGET_EFFECTIVE_SLOTS,
            "single_slot_risk_pct": 100.0 / TARGET_EFFECTIVE_SLOTS,
            "allowed_now": 0,
            "comment": "目标至少7个有效槽，单槽风险约14.3%。",
        },
    ]
    return pd.DataFrame(scenarios)


def _build_gates(
    product_rescreen: pd.DataFrame,
    family_rescreen: pd.DataFrame,
    slot_scenarios: pd.DataFrame,
    dce_decision: dict[str, Any],
) -> pd.DataFrame:
    deployable_new_slots = int(family_rescreen["deployable_new_slot_now"].sum())
    effective_now = int(
        slot_scenarios.loc[
            slot_scenarios["scenario"].eq("after_dce_blocker_current_state"),
            "effective_slots",
        ].iloc[0]
    )
    dce_blocked = str(dce_decision.get("decision", "")).endswith("source_blocked")
    source_rich_low_edge = int(product_rescreen["rescreen_status"].eq("source_rich_no_edge_monitor").sum())
    rows = [
        {
            "gate": "source_first_rescreen_completed",
            "threshold": "all Stage574/597 products classified",
            "actual": f"{len(product_rescreen)} products / {product_rescreen['product_family'].nunique()} families",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "完成source-first分层。",
        },
        {
            "gate": "no_new_return_backtest",
            "threshold": "no replay, no whitelist, no parameter scan",
            "actual": "read-only synthesis from frozen outputs",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "避免把后验收益排名直接升级成实盘规则。",
        },
        {
            "gate": "dce_blocker_accounted",
            "threshold": "Stage600 decision blocks j/i promotion",
            "actual": str(dce_decision.get("decision", "missing")),
            "passed": int(dce_blocked),
            "hard_gate": 1,
            "judgement": "DCE普通browser-cookie route已反证，black_ferrous不能计入当前可交易槽。",
        },
        {
            "gate": "deployable_new_family_slots_now",
            "threshold": ">=2 deployable new slots",
            "actual": f"{deployable_new_slots} deployable new slots",
            "passed": int(deployable_new_slots >= 2),
            "hard_gate": 1,
            "judgement": "当前没有新的可交易独立槽。",
        },
        {
            "gate": "effective_slots_after_dce_blocker",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS} effective slots",
            "actual": f"{effective_now} effective slots",
            "passed": int(effective_now >= TARGET_EFFECTIVE_SLOTS),
            "hard_gate": 1,
            "judgement": "DCE未解决时仍只有4槽。",
        },
        {
            "gate": "same_family_depth_not_counted",
            "threshold": "depth only does not increase slots",
            "actual": "same-family products keep effective slots unchanged",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "al/bu/TA/pg不被误计为独立风险槽。",
        },
        {
            "gate": "source_rich_low_edge_forward_only",
            "threshold": "source rich but no historical edge stays monitor-only",
            "actual": f"{source_rich_low_edge} products",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "有源无edge的族不投入TCA，不进入paper。",
        },
    ]
    return pd.DataFrame(rows)


def _build_next_actions(family_rescreen: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "priority": 1,
                "scope": "P0",
                "targets": "v.DCE,ao.SHFE,lu.INE,y.DCE/c.DCE",
                "action": "继续补route/event/official endpoint/TCA；y/c同族同向top1-only。",
                "stop_condition": "20个forward日期和9个P0 TCA样本未达标前禁止收益回测。",
            },
            {
                "priority": 2,
                "scope": "black_ferrous",
                "targets": "j.DCE,i.DCE",
                "action": "停止普通browser-cookie路线；只寻找可授权DCE源、交易所可下载替代源或稳定准官方源。",
                "stop_condition": "没有机器可读、point-in-time、可合规复跑的数据源则继续不paper。",
            },
            {
                "priority": 3,
                "scope": "same_family_depth",
                "targets": "al.SHFE,bu.SHFE,TA.CZCE,pg.DCE",
                "action": "只作为同族tie-break/替补证据，不计入新增风险槽；不做白名单。",
                "stop_condition": "除非同时新增独立族，否则不能改善单槽风险。",
            },
            {
                "priority": 4,
                "scope": "source_rich_no_edge",
                "targets": ",".join(
                    family_rescreen[
                        family_rescreen["family_status"].eq("source_rich_no_edge_monitor")
                    ]["product_family"].astype(str).tolist()
                )
                or "soft_agri,precious_metals",
                "action": "保留低频forward monitor；只有20日后出现固定事前selector edge才补TCA。",
                "stop_condition": "历史机会不足且forward edge未成熟时不进入回测。",
            },
            {
                "priority": 5,
                "scope": "new_family_search",
                "targets": "non-DCE low-corr families",
                "action": "下一轮优先找非DCE、source更稳定的新独立族；先做source/TCA，不做收益扫描。",
                "stop_condition": "若仍找不到两个新族，扩池目标必须转为外部承载工具或跨策略组合。",
            },
        ]
    )


def _build_decision(
    product_rescreen: pd.DataFrame,
    family_rescreen: pd.DataFrame,
    slot_scenarios: pd.DataFrame,
    gates: pd.DataFrame,
    dce_decision: dict[str, Any],
) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    effective_now = int(
        slot_scenarios.loc[
            slot_scenarios["scenario"].eq("after_dce_blocker_current_state"),
            "effective_slots",
        ].iloc[0]
    )
    effective_if_black = int(
        slot_scenarios.loc[
            slot_scenarios["scenario"].eq("if_black_ferrous_authorized_source_resolved"),
            "effective_slots",
        ].iloc[0]
    )
    return {
        "stage": "Stage301",
        "script_stage": "Stage601",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "source_first_rescreen_no_new_tradeable_slot",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "products_rescreened": int(len(product_rescreen)),
        "families_rescreened": int(family_rescreen["product_family"].nunique()),
        "effective_slots_now": effective_now,
        "effective_slots_if_black_ferrous_source_resolved": effective_if_black,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "deployable_new_family_slots_now": int(family_rescreen["deployable_new_slot_now"].sum()),
        "dce_stage600_decision": dce_decision.get("decision", "missing"),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "main_judgement": (
            "扩池方向仍成立，但DCE阻塞后当前没有新的可交易独立风险槽；"
            "al/bu/TA/pg是同族深度，source-rich低edge家族只能monitor。"
        ),
        "overfit_boundary": "No new replay, no top-N scan, no whitelist; only source/correlation/capacity/TCA synthesis.",
        "next_step": "Search non-DCE source-stable low-corr families or authorized DCE source; keep P0 source/TCA collection active.",
    }


def _plot(product_rescreen: pd.DataFrame, family_rescreen: pd.DataFrame, slot_scenarios: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle("Stage601 source-first risk-slot rescreen", fontsize=16)

    ax = axes[0, 0]
    color_map = {
        "P0_existing_slot_incomplete": "#1f77b4",
        "new_slot_blocked_by_dce_source": "#ff7f0e",
        "same_family_depth_not_slot": "#2ca02c",
        "reject_high_core_corr": "#d62728",
        "source_rich_no_edge_monitor": "#9467bd",
        "no_material_opportunity_monitor": "#8c564b",
        "reject_capacity_or_liquidity": "#7f7f7f",
        "observe_only": "#bcbd22",
    }
    for status, group in product_rescreen.groupby("rescreen_status", sort=False):
        ax.scatter(
            group["abs_core_daily_pnl_corr"],
            group["total_pnl"],
            s=np.clip(group["source_component_pct"].fillna(0) * 4 + 50, 50, 420),
            alpha=0.76,
            color=color_map.get(status, "#17becf"),
            edgecolor="black",
            linewidth=0.35,
            label=status,
        )
        for _, row in group.iterrows():
            if float(row["total_pnl"]) >= 10_000 or status in {"new_slot_blocked_by_dce_source", "reject_high_core_corr"}:
                ax.annotate(str(row["product_vt_symbol"]), (row["abs_core_daily_pnl_corr"], row["total_pnl"]), fontsize=8)
    ax.axvline(MAX_CORE_CORR_WATCH, color="red", linestyle="--", linewidth=1)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Product opportunity vs core correlation")
    ax.set_xlabel("abs core daily PnL corr")
    ax.set_ylabel("single-product total PnL")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7, loc="best")

    ax = axes[0, 1]
    view = family_rescreen.head(12).copy()
    y = np.arange(len(view))
    colors = {
        "P0_existing_slot_incomplete": "#1f77b4",
        "P1_new_slot_blocked_by_dce_source": "#ff7f0e",
        "same_family_depth_not_slot": "#2ca02c",
        "reject_high_core_corr": "#d62728",
        "source_rich_no_edge_monitor": "#9467bd",
        "positive_but_not_operational_slot": "#8c564b",
        "no_current_slot_value": "#7f7f7f",
    }
    short_status = {
        "P0_existing_slot_incomplete": "P0 slot",
        "P1_new_slot_blocked_by_dce_source": "DCE blocked",
        "same_family_depth_not_slot": "depth only",
        "reject_high_core_corr": "high corr",
        "source_rich_no_edge_monitor": "source/no edge",
        "positive_but_not_operational_slot": "not operational",
        "no_current_slot_value": "no slot",
    }
    ax.barh(
        y,
        view["best_source_first_score"],
        color=[colors.get(item, "#17becf") for item in view["family_status"]],
        alpha=0.88,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(view["product_family"])
    ax.invert_yaxis()
    ax.set_title("Family source-first score (worklist ranking only)")
    ax.set_xlabel("score")
    for idx, row in view.iterrows():
        ax.text(
            float(row["best_source_first_score"]) + 1,
            list(view.index).index(idx),
            short_status.get(str(row["family_status"]), str(row["family_status"])),
            va="center",
            fontsize=8,
        )
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 0]
    slot_view = slot_scenarios.copy()
    slot_label_map = {
        "current_P0_effective_after_yc_top1": "P0 now",
        "after_same_family_depth": "+ depth",
        "after_dce_blocker_current_state": "DCE blocked",
        "if_black_ferrous_authorized_source_resolved": "if j/i source",
        "preferred_target": "target",
    }
    bar_colors = np.where(slot_view["allowed_now"].eq(1), "#ffbf00", "#2ca02c")
    bars = ax.bar(slot_view["scenario"].map(slot_label_map).fillna(slot_view["scenario"]), slot_view["single_slot_risk_pct"], color=bar_colors)
    ax.axhline(TARGET_MAX_SLOT_RISK_PCT, color="green", linestyle="--", label="15% target")
    ax.set_title("Effective slot pressure after DCE blocker")
    ax.set_ylabel("risk per effective slot (%)")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(fontsize=8)
    for bar, (_, row) in zip(bars, slot_view.iterrows()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            float(row["single_slot_risk_pct"]) + 0.6,
            f"{row['effective_slots']} slots\n{row['single_slot_risk_pct']:.1f}%",
            ha="center",
            fontsize=8,
        )
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    gate_view = gates.copy()
    gate_colors = np.where(gate_view["passed"].eq(1), "#2ca02c", "#d62728")
    ax.barh(gate_view["gate"], np.ones(len(gate_view)), color=gate_colors, alpha=0.9)
    for idx, row in gate_view.iterrows():
        ax.text(
            0.5,
            idx,
            "PASS" if int(row["passed"]) else "FAIL",
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
            fontsize=8,
        )
    ax.set_title("Gates: no paper / no whitelist")
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.grid(axis="x", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _build_report(
    decision: dict[str, Any],
    product_rescreen: pd.DataFrame,
    family_rescreen: pd.DataFrame,
    slot_scenarios: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
    source_priority: pd.DataFrame,
) -> str:
    return f"""# Stage301 risk-slot source-first rescreen

- 生成时间：`{decision["generated_at_local"]}`
- 决策：`{decision["decision"]}`
- 阶段性质：只读合成 Stage574/571/597/600 证据；不做收益回放、不改策略、不生成交易白名单。
- 调研参考：
{chr(10).join(f"  - {item}" for item in REFERENCE_LINKS)}

## 结论

- 扩池降低单笔风险的方向继续成立，但 DCE 官方源被 Stage599/600 反证后，当前没有新的可交易独立风险槽。
- 当前 P0 仍只有 `4` 个有效槽；`al/bu/TA/pg` 是同族深度，不增加槽；`black_ferrous(j/i)` 如果未来解决可授权/稳定数据源，最多把槽数推到 `5`，仍低于目标 `7`。
- `soft_agri/precious_metals` 等 source 相对完整且相关低，但当前历史机会为负或不足，只允许 forward monitor，不能投入 TCA 或 paper。
- 因此下一步不应继续扫宽池收益，而应转向两个动作：一是找非 DCE 且 source 稳定的新低相关产品族；二是继续 P0 和 Stage526 的真实 TCA 闭环。

## Product Rescreen

{_md_table(product_rescreen, [
    "product_vt_symbol",
    "product_family",
    "rescreen_status",
    "tier",
    "total_pnl",
    "positive_year_rate_pct",
    "abs_core_daily_pnl_corr",
    "source_component_pct",
    "capacity_quality_flag",
    "source_first_score",
    "whitelist_allowed",
], max_rows=32)}

## Family Rescreen

{_md_table(family_rescreen, [
    "product_family",
    "family_status",
    "products",
    "product_list",
    "best_source_first_product",
    "best_source_first_score",
    "family_positive_pnl_sum",
    "family_max_abs_core_corr",
    "source_rich_products",
    "deployable_new_slot_now",
    "judgement",
], max_rows=20)}

## Slot Scenarios

{_md_table(slot_scenarios)}

## Gates

{_md_table(gates)}

## Source Priority Context

{_md_table(source_priority, [
    "source_route",
    "latest_forward_ready_products",
    "history_ready_products",
    "qualified_forward_runs",
    "qualified_forward_dates",
    "recommended_action",
], max_rows=10)}

## Next Actions

{_md_table(next_actions)}

## 输出

- product rescreen：`{PRODUCT_RESCREEN_PATH}`
- family rescreen：`{FAMILY_RESCREEN_PATH}`
- slot scenarios：`{SLOT_SCENARIO_PATH}`
- gates：`{GATES_PATH}`
- next actions：`{NEXT_ACTIONS_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""


def main() -> None:
    product_rescreen = _load_product_rescreen()
    family_rescreen = _build_family_rescreen(product_rescreen)
    slot_scenarios = _build_slot_scenarios(family_rescreen)
    dce_decision = _read_json(STAGE600_DECISION)
    gates = _build_gates(product_rescreen, family_rescreen, slot_scenarios, dce_decision)
    next_actions = _build_next_actions(family_rescreen)
    decision = _build_decision(product_rescreen, family_rescreen, slot_scenarios, gates, dce_decision)
    source_priority = _read_csv(STAGE571_SOURCE_PRIORITY)
    report = _build_report(decision, product_rescreen, family_rescreen, slot_scenarios, gates, next_actions, source_priority)

    PRODUCT_RESCREEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    product_rescreen.to_csv(PRODUCT_RESCREEN_PATH, index=False, encoding="utf-8-sig")
    family_rescreen.to_csv(FAMILY_RESCREEN_PATH, index=False, encoding="utf-8-sig")
    slot_scenarios.to_csv(SLOT_SCENARIO_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _plot(product_rescreen, family_rescreen, slot_scenarios, gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2, sort_keys=True))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
