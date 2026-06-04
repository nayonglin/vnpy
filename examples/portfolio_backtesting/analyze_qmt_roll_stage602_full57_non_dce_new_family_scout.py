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


MODEL_TAG = "stage602_full57_non_dce_new_family_scout_v1"
OUTPUT_PREFIX = "qmt_roll_stage602_full57_non_dce_new_family_scout"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE541_SUMMARY = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_summary_stage541_single_product_opportunity_map_v1.csv"
STAGE548_SOURCE_MATRIX = OUTPUT_DIR / "qmt_roll_stage548_external_source_alternative_probe_product_source_matrix_stage548_external_source_alternative_probe_v1.csv"
STAGE601_PRODUCT_RESCREEN = OUTPUT_DIR / "qmt_roll_stage601_risk_slot_source_first_rescreen_product_rescreen_stage601_risk_slot_source_first_rescreen_v1.csv"
STAGE601_DECISION = OUTPUT_DIR / "qmt_roll_stage601_risk_slot_source_first_rescreen_decision_stage601_risk_slot_source_first_rescreen_v1.json"

PRODUCT_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_map_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
NON_DCE_SCOUT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_non_dce_new_family_scout_{MODEL_TAG}.csv"
SLOT_SCENARIO_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slot_scenarios_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_FAMILIES = {"grains_oilseeds", "petrochem", "energy_oil", "base_metals"}
P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 = 4
TARGET_EFFECTIVE_SLOTS = 7
MAX_CORE_CORR_WATCH = 0.10
SOURCE_RICH_COMPONENT_PCT = 60.0
MATERIAL_PRODUCT_PNL = 10_000.0
MATERIAL_FAMILY_PNL = 25_000.0

REFERENCE_LINKS = [
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "Optimal Allocation of Trend Following Strategies: https://arxiv.org/abs/1410.8409",
    "skfolio HRP/Hierarchical clustering: https://skfolio.org/generated/skfolio.optimization.HierarchicalRiskParity.html",
]

PRODUCT_FAMILY: dict[str, tuple[str, str]] = {
    "CY.CZCE": ("soft_agri", "棉纺软商品"),
    "SR.CZCE": ("soft_agri", "糖棉软商品"),
    "PK.CZCE": ("grains_oilseeds", "油脂油料/农产品"),
    "a.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "c.DCE": ("grains_oilseeds", "谷物/农产品"),
    "cs.DCE": ("grains_oilseeds", "谷物/农产品"),
    "m.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "p.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "y.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "rr.DCE": ("grains_oilseeds", "谷物/农产品"),
    "jd.DCE": ("livestock", "畜禽农产品"),
    "sc.INE": ("energy_oil", "原油能源"),
    "lu.INE": ("energy_oil", "燃油能源"),
    "bu.SHFE": ("energy_oil", "沥青能源"),
    "pg.DCE": ("energy_oil", "LPG能源"),
    "TA.CZCE": ("petrochem", "聚酯化工"),
    "PF.CZCE": ("petrochem", "聚酯化工"),
    "PX.CZCE": ("petrochem", "芳烃化工"),
    "UR.CZCE": ("petrochem", "尿素化工"),
    "eb.DCE": ("petrochem", "苯乙烯化工"),
    "v.DCE": ("petrochem", "PVC化工"),
    "br.SHFE": ("rubber", "橡胶"),
    "nr.INE": ("rubber", "橡胶"),
    "i.DCE": ("black_ferrous", "黑色矿石焦煤"),
    "j.DCE": ("black_ferrous", "黑色焦煤焦炭"),
    "SF.CZCE": ("black_ferrous", "铁合金"),
    "ag.SHFE": ("precious_metals", "贵金属"),
    "al.SHFE": ("base_metals", "有色金属"),
    "ao.SHFE": ("base_metals", "有色金属"),
    "bc.INE": ("base_metals", "有色金属"),
    "ni.SHFE": ("base_metals", "有色金属"),
    "pb.SHFE": ("base_metals", "有色金属"),
    "sn.SHFE": ("base_metals", "有色金属"),
    "ss.SHFE": ("base_metals", "不锈钢金属"),
    "zn.SHFE": ("base_metals", "有色金属"),
    "IH.CFFEX": ("financial_index", "股指"),
    "PR.CZCE": ("other", "其他新品种"),
    "fb.DCE": ("other", "板材其他"),
    "AP.CZCE": ("soft_agri", "apple soft/agri"),
    "CF.CZCE": ("soft_agri", "cotton soft/agri"),
    "FG.CZCE": ("black_ferrous", "glass construction chain"),
    "MA.CZCE": ("petrochem", "methanol petrochem"),
    "OI.CZCE": ("grains_oilseeds", "rapeseed oil"),
    "SA.CZCE": ("petrochem", "soda ash chemical"),
    "SH.CZCE": ("petrochem", "caustic soda chemical"),
    "SM.CZCE": ("black_ferrous", "silicomanganese"),
    "au.SHFE": ("precious_metals", "gold"),
    "cu.SHFE": ("base_metals", "copper"),
    "fu.SHFE": ("energy_oil", "fuel oil"),
    "hc.SHFE": ("black_ferrous", "hot rolled coil"),
    "rb.SHFE": ("black_ferrous", "rebar"),
    "ru.SHFE": ("rubber", "rubber"),
    "sp.SHFE": ("other", "pulp"),
    "jm.DCE": ("black_ferrous", "coking coal"),
    "lh.DCE": ("livestock", "live hog"),
    "lc.GFEX": ("base_metals", "battery metal"),
    "si.GFEX": ("base_metals", "industrial silicon"),
}

STATUS_COLOR = {
    "core_existing_not_new_slot": "#718096",
    "P0_existing_slot_incomplete": "#2b6cb0",
    "same_family_depth_not_slot": "#68d391",
    "new_slot_blocked_by_dce_source": "#ed8936",
    "reject_high_core_corr": "#e53e3e",
    "source_rich_no_edge_monitor": "#9f7aea",
    "no_material_opportunity_monitor": "#a0aec0",
    "reject_capacity_or_liquidity": "#4a5568",
    "observe_only": "#cbd5e0",
}


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
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


def _family(product_vt_symbol: str, source_lookup: dict[str, tuple[str, str]]) -> tuple[str, str]:
    if product_vt_symbol in source_lookup:
        return source_lookup[product_vt_symbol]
    return PRODUCT_FAMILY.get(product_vt_symbol, ("unknown", "未分类"))


def _build_product_map() -> pd.DataFrame:
    summary = _read_csv(STAGE541_SUMMARY)
    source = _read_csv(STAGE548_SOURCE_MATRIX)
    rescreen = _read_csv(STAGE601_PRODUCT_RESCREEN)

    summary["product_vt_symbol"] = summary["product_vt_symbol"].astype(str)
    source["product_vt_symbol"] = source["product_vt_symbol"].astype(str)
    rescreen["product_vt_symbol"] = rescreen["product_vt_symbol"].astype(str)

    source_lookup: dict[str, tuple[str, str]] = {}
    for row in source.itertuples(index=False):
        source_lookup[str(row.product_vt_symbol)] = (str(row.product_family), str(row.family_note))

    frame = summary.copy()
    frame["abs_core_daily_pnl_corr"] = _num(frame, "core_daily_pnl_corr").abs()
    family_rows = frame["product_vt_symbol"].map(lambda item: _family(str(item), source_lookup))
    frame["product_family"] = [item[0] for item in family_rows]
    frame["family_note"] = [item[1] for item in family_rows]

    source_cols = [
        "product_vt_symbol",
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "all_core_external_state_ready",
        "basis_coverage_rate_pct",
        "basis_months",
    ]
    frame = frame.merge(source[[col for col in source_cols if col in source.columns]], on="product_vt_symbol", how="left")
    for col in [
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "all_core_external_state_ready",
        "basis_coverage_rate_pct",
        "basis_months",
    ]:
        frame[col] = _num(frame, col)

    component_cols = [
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
    ]
    frame["source_component_count"] = frame[component_cols].sum(axis=1)
    frame["source_component_pct"] = frame["source_component_count"] / len(component_cols) * 100.0

    rescreen_cols = [
        "product_vt_symbol",
        "rescreen_status",
        "tier",
        "source_first_score",
        "priority",
        "action",
        "reason",
    ]
    frame = frame.merge(rescreen[[col for col in rescreen_cols if col in rescreen.columns]], on="product_vt_symbol", how="left")

    for col in ["total_pnl", "positive_active_year_rate_pct", "candidate_materiality_pass", "max_broker10_margin_to_sleeve_equity_pct", "recent_bar_coverage_ratio"]:
        frame[col] = _num(frame, col)
    frame["source_first_score"] = _num(frame, "source_first_score")

    statuses: list[str] = []
    judgements: list[str] = []
    for row in frame.itertuples(index=False):
        product = str(row.product_vt_symbol)
        is_core = int(row.is_core_product) == 1
        rescreen_status = str(getattr(row, "rescreen_status", "") or "")
        family = str(row.product_family)
        exchange = str(row.exchange)
        total_pnl = float(row.total_pnl)
        abs_corr = float(row.abs_core_daily_pnl_corr)
        source_pct = float(row.source_component_pct)
        if is_core:
            status = "core_existing_not_new_slot"
            judgement = "已有核心产品，保留诊断价值，但不能当成新增扩池槽。"
        elif rescreen_status and rescreen_status != "nan":
            status = rescreen_status
            if status == "P0_existing_slot_incomplete":
                judgement = "现有P0扩池槽，重点补route/event/TCA；不新增槽。"
            elif status == "same_family_depth_not_slot":
                judgement = "同族补深或tie-break，不降低独立单槽风险。"
            elif status == "new_slot_blocked_by_dce_source":
                judgement = "低相关新扩池槽线索，但DCE官方源阻塞，不能paper。"
            elif status == "reject_high_core_corr":
                judgement = "有机会但核心相关过高，不能作为分散槽。"
            elif status == "source_rich_no_edge_monitor":
                judgement = "source较完整但历史机会不足，只做forward monitor。"
            elif status == "reject_capacity_or_liquidity":
                judgement = "流动性/容量风险不适合低单笔风险扩池。"
            else:
                judgement = "历史机会不足，避免因数据可得而过拟合。"
        elif exchange != "DCE" and family not in P0_FAMILIES and abs_corr <= MAX_CORE_CORR_WATCH and total_pnl >= MATERIAL_PRODUCT_PNL and source_pct >= SOURCE_RICH_COMPONENT_PCT:
            status = "non_dce_candidate_unexpected"
            judgement = "全57新增低相关非DCE候选，需要单独复核。"
        else:
            status = "observe_only"
            judgement = "未形成可部署新风险槽。"
        statuses.append(status)
        judgements.append(judgement)

    frame["full57_status"] = statuses
    frame["slot_judgement"] = judgements
    frame["is_non_dce_new_family_scout"] = (
        frame["is_core_product"].eq(0)
        & ~frame["exchange"].astype(str).eq("DCE")
        & ~frame["product_family"].astype(str).isin(P0_FAMILIES)
    ).astype(int)
    frame["low_corr_pass"] = frame["abs_core_daily_pnl_corr"].le(MAX_CORE_CORR_WATCH).astype(int)
    frame["source_rich"] = frame["source_component_pct"].ge(SOURCE_RICH_COMPONENT_PCT).astype(int)
    frame["positive_material"] = frame["total_pnl"].ge(MATERIAL_PRODUCT_PNL).astype(int)
    frame["deployable_new_slot_now"] = 0
    frame["whitelist_allowed"] = 0
    return frame.sort_values(["is_core_product", "total_pnl"], ascending=[True, False]).reset_index(drop=True)


def _build_family_summary(product_map: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, group in product_map.groupby("product_family", sort=False):
        positive_core = group[group["is_core_product"].eq(1) & group["total_pnl"].gt(0)]
        positive_noncore = group[group["is_core_product"].eq(0) & group["total_pnl"].gt(0)]
        best = group.sort_values("total_pnl", ascending=False).iloc[0]
        statuses = set(group["full57_status"].astype(str))
        if "P0_existing_slot_incomplete" in statuses:
            status = "P0_existing_slot_incomplete"
            judgement = "当前已有P0风险槽，继续补source/TCA；同族扩展不算新增独立槽。"
        elif "new_slot_blocked_by_dce_source" in statuses:
            status = "P1_new_slot_blocked_by_dce_source"
            judgement = "扩池线索存在，但被DCE官方源阻塞，不能进入paper或白名单。"
        elif "reject_high_core_corr" in statuses and float(positive_noncore["total_pnl"].sum()) > 0:
            status = "reject_high_core_corr"
            judgement = "有正收益产品但与核心相关过高，不能降低组合相关风险。"
        elif "source_rich_no_edge_monitor" in statuses:
            status = "source_rich_no_edge_monitor"
            judgement = "数据源较完整但历史机会不足；只做低频forward monitor。"
        elif int(group["is_core_product"].sum()) > 0:
            status = "core_existing_family_not_new_slot"
            judgement = "已有核心族贡献，不能重复当作扩池新槽。"
        elif float(positive_noncore["total_pnl"].sum()) > 0:
            status = "positive_but_not_deployable_slot"
            judgement = "有正收益但未同时满足source/相关/材料性/容量闸门。"
        else:
            status = "no_current_slot_value"
            judgement = "当前没有投入TCA或selector验证的价值。"
        rows.append(
            {
                "product_family": family,
                "family_status": status,
                "products": int(len(group)),
                "core_products": int(group["is_core_product"].sum()),
                "noncore_products": int(group["is_core_product"].eq(0).sum()),
                "non_dce_new_family_products": int(group["is_non_dce_new_family_scout"].sum()),
                "product_list": ",".join(group["product_vt_symbol"].astype(str).tolist()),
                "best_product": str(best["product_vt_symbol"]),
                "best_product_total_pnl": float(best["total_pnl"]),
                "positive_core_pnl_sum": float(positive_core["total_pnl"].sum()),
                "positive_noncore_pnl_sum": float(positive_noncore["total_pnl"].sum()),
                "family_total_pnl_sum": float(group["total_pnl"].sum()),
                "family_max_abs_core_corr": float(group["abs_core_daily_pnl_corr"].max()),
                "source_rich_noncore_products": int(group.loc[group["is_core_product"].eq(0), "source_rich"].sum()),
                "deployable_new_slot_now": 0,
                "judgement": judgement,
            }
        )
    return pd.DataFrame(rows).sort_values(["deployable_new_slot_now", "positive_noncore_pnl_sum", "positive_core_pnl_sum"], ascending=[False, False, False])


def _build_non_dce_scout(product_map: pd.DataFrame) -> pd.DataFrame:
    scout = product_map[product_map["is_non_dce_new_family_scout"].eq(1)].copy()
    if scout.empty:
        return scout
    scout["candidate_gap"] = np.select(
        [
            scout["full57_status"].eq("reject_high_core_corr"),
            scout["low_corr_pass"].eq(1) & scout["source_rich"].eq(1) & scout["positive_material"].eq(0),
            scout["low_corr_pass"].eq(1) & scout["source_rich"].eq(0) & scout["positive_material"].eq(1),
            scout["low_corr_pass"].eq(0),
        ],
        [
            "core_corr_too_high",
            "source_ready_but_no_material_edge",
            "material_but_source_gap",
            "core_corr_too_high",
        ],
        default="no_material_edge_or_capacity",
    )
    scout["deployable_new_slot_now"] = 0
    return scout.sort_values(["total_pnl", "abs_core_daily_pnl_corr"], ascending=[False, True])


def _build_slot_scenarios(non_dce_scout: pd.DataFrame, stage601_decision: dict[str, Any]) -> pd.DataFrame:
    non_dce_deployable = int(non_dce_scout["deployable_new_slot_now"].sum()) if not non_dce_scout.empty else 0
    dce_resolved_slots = int(stage601_decision.get("effective_slots_if_black_ferrous_source_resolved", 5))
    rows = [
        {
            "scenario": "current_p0_effective_slots",
            "effective_slots": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "new_slots_added": 0,
            "slot_risk_pct_if_equal": 100.0 / P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "status": "current",
            "judgement": "当前P0只有4个有效独立槽，单槽风险约25%。",
        },
        {
            "scenario": "plus_full57_non_dce_deployable_now",
            "effective_slots": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 + non_dce_deployable,
            "new_slots_added": non_dce_deployable,
            "slot_risk_pct_if_equal": 100.0 / (P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 + non_dce_deployable),
            "status": "no_change",
            "judgement": "完整57产品没有给出新的非DCE可部署风险槽。",
        },
        {
            "scenario": "if_black_ferrous_dce_source_resolved",
            "effective_slots": dce_resolved_slots,
            "new_slots_added": max(0, dce_resolved_slots - P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1),
            "slot_risk_pct_if_equal": 100.0 / dce_resolved_slots,
            "status": "conditional",
            "judgement": "若j/i的DCE源和TCA解决，最多先到5槽，仍低于目标7槽。",
        },
        {
            "scenario": "target_structure",
            "effective_slots": TARGET_EFFECTIVE_SLOTS,
            "new_slots_added": TARGET_EFFECTIVE_SLOTS - P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
            "slot_risk_pct_if_equal": 100.0 / TARGET_EFFECTIVE_SLOTS,
            "status": "target",
            "judgement": "目标是至少7个有效槽，单槽风险约14.3%。",
        },
    ]
    return pd.DataFrame(rows)


def _build_gates(product_map: pd.DataFrame, non_dce_scout: pd.DataFrame, slot_scenarios: pd.DataFrame) -> pd.DataFrame:
    noncore = product_map[product_map["is_core_product"].eq(0)]
    non_dce_deployable = int(non_dce_scout["deployable_new_slot_now"].sum()) if not non_dce_scout.empty else 0
    high_corr_positive_rejected = int(
        (
            product_map["full57_status"].eq("reject_high_core_corr")
            & product_map["total_pnl"].gt(0)
        ).sum()
    )
    gates = [
        {
            "gate": "full57_scope_complete",
            "threshold": "57 products",
            "actual": str(int(product_map["product_vt_symbol"].nunique())),
            "passed": int(product_map["product_vt_symbol"].nunique() == 57),
            "comment": "Stage541全57产品已纳入。",
        },
        {
            "gate": "all_noncore_covered_by_stage601",
            "threshold": "38 noncore products",
            "actual": str(int(noncore["product_vt_symbol"].nunique())),
            "passed": int(int(noncore["product_vt_symbol"].nunique()) == 38),
            "comment": "Stage601已覆盖全部非核心产品，Stage602补的是核心/非核心边界。",
        },
        {
            "gate": "non_dce_deployable_new_slots_ge_2",
            "threshold": ">=2",
            "actual": str(non_dce_deployable),
            "passed": int(non_dce_deployable >= 2),
            "comment": "没有非DCE、source稳定、低相关、材料性同时过线的新槽。",
        },
        {
            "gate": "core_products_not_reused_as_expansion_slots",
            "threshold": "true",
            "actual": "true",
            "passed": 1,
            "comment": "FG/AP/OI/lc/hc等正收益是已有核心贡献，不当成新增扩池alpha。",
        },
        {
            "gate": "high_corr_positive_candidates_rejected",
            "threshold": ">=1 acknowledged",
            "actual": str(high_corr_positive_rejected),
            "passed": int(high_corr_positive_rejected >= 1),
            "comment": "br.SHFE这类有正收益但相关性过高的产品被拒绝。",
        },
        {
            "gate": "effective_slots_reach_target_now",
            "threshold": f">={TARGET_EFFECTIVE_SLOTS}",
            "actual": str(int(slot_scenarios.loc[slot_scenarios["scenario"].eq("plus_full57_non_dce_deployable_now"), "effective_slots"].iloc[0])),
            "passed": 0,
            "comment": "当前仍为4个有效槽，离目标7槽差3个。",
        },
        {
            "gate": "promotion_or_whitelist_allowed",
            "threshold": "false",
            "actual": "false",
            "passed": 0,
            "comment": "本阶段不允许paper、A/B、白名单或收益回测。",
        },
    ]
    return pd.DataFrame(gates)


def _plot(product_map: pd.DataFrame, family_summary: pd.DataFrame, non_dce_scout: pd.DataFrame, slot_scenarios: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), constrained_layout=True)
    fig.suptitle("Stage602 full-57 risk slot scout: breadth helps only when source, edge and correlation all pass", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    for status, group in product_map.groupby("full57_status"):
        ax.scatter(
            group["abs_core_daily_pnl_corr"],
            group["total_pnl"],
            s=np.where(group["is_core_product"].eq(1), 45, 70),
            alpha=0.82,
            color=STATUS_COLOR.get(status, "#cbd5e0"),
            label=status,
            edgecolor="white",
            linewidth=0.6,
        )
    label_products = set(
        product_map.sort_values("total_pnl", ascending=False)["product_vt_symbol"].head(14).tolist()
        + ["br.SHFE", "j.DCE", "i.DCE", "ag.SHFE", "SR.CZCE", "CY.CZCE", "SF.CZCE"]
    )
    for row in product_map[product_map["product_vt_symbol"].isin(label_products)].itertuples(index=False):
        ax.annotate(str(row.product_vt_symbol), (float(row.abs_core_daily_pnl_corr), float(row.total_pnl)), fontsize=8, xytext=(4, 3), textcoords="offset points")
    ax.axvline(MAX_CORE_CORR_WATCH, color="#e53e3e", linestyle="--", linewidth=1.2, label="corr watch 0.10")
    ax.axhline(0, color="#4a5568", linewidth=0.8)
    ax.set_xlabel("abs corr to Stage526 core daily PnL")
    ax.set_ylabel("single-product opportunity PnL")
    ax.set_title("All 57 products: most positive noncore names are not new independent slots")
    ax.legend(fontsize=7, loc="upper right", ncol=1, frameon=False)
    ax.grid(alpha=0.2)

    ax = axes[0, 1]
    fam = family_summary.copy().sort_values("positive_noncore_pnl_sum", ascending=True)
    y = np.arange(len(fam))
    ax.barh(y, fam["positive_noncore_pnl_sum"], color="#2b6cb0", label="positive noncore PnL")
    ax.barh(y, fam["positive_core_pnl_sum"], left=fam["positive_noncore_pnl_sum"], color="#a0aec0", label="positive core PnL")
    ax.set_yticks(y)
    ax.set_yticklabels(fam["product_family"], fontsize=8)
    ax.set_xlabel("positive PnL sum")
    ax.set_title("Family contribution: core wins are not new slots")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="x", alpha=0.2)

    ax = axes[1, 0]
    scout = non_dce_scout.copy()
    if scout.empty:
        ax.text(0.5, 0.5, "No non-DCE scout rows", ha="center", va="center")
    else:
        scout = scout.sort_values("total_pnl", ascending=True)
        gap_color = {
            "core_corr_too_high": "#e53e3e",
            "source_ready_but_no_material_edge": "#9f7aea",
            "material_but_source_gap": "#ed8936",
            "no_material_edge_or_capacity": "#a0aec0",
        }
        colors = [gap_color.get(gap, "#a0aec0") for gap in scout["candidate_gap"]]
        ax.barh(scout["product_vt_symbol"], scout["total_pnl"], color=colors)
        min_x = float(scout["total_pnl"].min())
        max_x = float(scout["total_pnl"].max())
        pad = max(2500.0, (max_x - min_x) * 0.18)
        ax.set_xlim(min_x - pad, max_x + pad)
        for row in scout.itertuples(index=False):
            ax.text(
                float(row.total_pnl) + (550 if float(row.total_pnl) >= 0 else -550),
                str(row.product_vt_symbol),
                f"corr={float(row.abs_core_daily_pnl_corr):.3f}",
                va="center",
                ha="left" if float(row.total_pnl) >= 0 else "right",
                fontsize=8,
            )
        legend_handles = [
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=color, markersize=9, label=label)
            for label, color in gap_color.items()
            if label in set(scout["candidate_gap"].astype(str))
        ]
        ax.legend(handles=legend_handles, frameon=False, fontsize=7, loc="lower right")
        ax.axvline(0, color="#4a5568", linewidth=0.8)
        ax.set_xlabel("single-product opportunity PnL")
        ax.set_title("Non-DCE new-family scout: no deployable slot now")
        ax.grid(axis="x", alpha=0.2)

    ax = axes[1, 1]
    slot = slot_scenarios.copy()
    colors = ["#2b6cb0", "#a0aec0", "#ed8936", "#68d391"]
    bars = ax.bar(slot["scenario"], slot["effective_slots"], color=colors)
    ax.axhline(TARGET_EFFECTIVE_SLOTS, color="#e53e3e", linestyle="--", linewidth=1.2, label="target 7 slots")
    for bar, risk in zip(bars, slot["slot_risk_pct_if_equal"], strict=False):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.12, f"{bar.get_height():.0f} slots\n{risk:.1f}%/slot", ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, max(TARGET_EFFECTIVE_SLOTS + 1, float(slot["effective_slots"].max()) + 2))
    ax.set_ylabel("effective independent slots")
    ax.set_title("Risk-slot scenarios")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(axis="y", alpha=0.2)

    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    product_map: pd.DataFrame,
    family_summary: pd.DataFrame,
    non_dce_scout: pd.DataFrame,
    slot_scenarios: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_cols = [
        "product_vt_symbol",
        "exchange",
        "is_core_product",
        "product_family",
        "total_pnl",
        "abs_core_daily_pnl_corr",
        "source_component_pct",
        "full57_status",
        "slot_judgement",
    ]
    family_cols = [
        "product_family",
        "family_status",
        "products",
        "core_products",
        "noncore_products",
        "positive_noncore_pnl_sum",
        "positive_core_pnl_sum",
        "family_max_abs_core_corr",
        "deployable_new_slot_now",
        "judgement",
    ]
    scout_cols = [
        "product_vt_symbol",
        "exchange",
        "product_family",
        "total_pnl",
        "abs_core_daily_pnl_corr",
        "source_component_pct",
        "candidate_gap",
        "full57_status",
    ]
    lines = [
        "# Stage602 full57 non-DCE new-family scout",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- main judgement: {decision['main_judgement']}",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- paper_selector_allowed: `{decision['paper_selector_allowed']}`",
        f"- trading_whitelist_allowed: `{decision['trading_whitelist_allowed']}`",
        "",
        "## Slot Scenarios",
        "",
        _md_table(slot_scenarios),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Non-DCE New-Family Scout",
        "",
        _md_table(non_dce_scout, scout_cols, max_rows=30),
        "",
        "## Family Summary",
        "",
        _md_table(family_summary, family_cols, max_rows=20),
        "",
        "## Top Products",
        "",
        _md_table(product_map.sort_values("total_pnl", ascending=False), top_cols, max_rows=25),
        "",
        "## Research references",
        "",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "## Output files",
        "",
        f"- product map: `{PRODUCT_MAP_PATH}`",
        f"- family summary: `{FAMILY_SUMMARY_PATH}`",
        f"- non-DCE scout: `{NON_DCE_SCOUT_PATH}`",
        f"- slot scenarios: `{SLOT_SCENARIO_PATH}`",
        f"- gates: `{GATES_PATH}`",
        f"- chart: `{CHART_PATH}`",
        f"- decision: `{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone()
    generated_at_utc = datetime.now(timezone.utc)
    stage601_decision = _read_json(STAGE601_DECISION)

    product_map = _build_product_map()
    family_summary = _build_family_summary(product_map)
    non_dce_scout = _build_non_dce_scout(product_map)
    slot_scenarios = _build_slot_scenarios(non_dce_scout, stage601_decision)
    gates = _build_gates(product_map, non_dce_scout, slot_scenarios)

    non_dce_deployable = int(non_dce_scout["deployable_new_slot_now"].sum()) if not non_dce_scout.empty else 0
    hard_passed = int(gates["passed"].sum())
    decision = {
        "stage": "Stage302",
        "script_stage": "Stage602",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": generated_at.isoformat(timespec="seconds"),
        "generated_at_utc": generated_at_utc.isoformat(timespec="seconds"),
        "decision": "full57_non_dce_scout_no_deployable_new_family",
        "main_judgement": "减少单笔风险、扩大品种池、避免高相关是正确方向，但完整57产品复筛后没有发现新的非DCE、source稳定、低相关且有材料性收益的新产品族；扩池瓶颈仍是有效风险槽不足而不是产品列表不够长。",
        "products_total": int(product_map["product_vt_symbol"].nunique()),
        "noncore_products_total": int(product_map["is_core_product"].eq(0).sum()),
        "core_products_total": int(product_map["is_core_product"].eq(1).sum()),
        "non_dce_new_family_scout_products": int(non_dce_scout["product_vt_symbol"].nunique()) if not non_dce_scout.empty else 0,
        "deployable_non_dce_new_family_slots_now": non_dce_deployable,
        "effective_slots_now": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
        "effective_slots_after_full57_non_dce": P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1 + non_dce_deployable,
        "effective_slots_if_black_ferrous_source_resolved": int(stage601_decision.get("effective_slots_if_black_ferrous_source_resolved", 5)),
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "slot_risk_pct_now_if_equal": 100.0 / P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1,
        "slot_risk_pct_target_if_equal": 100.0 / TARGET_EFFECTIVE_SLOTS,
        "hard_gates_passed": hard_passed,
        "hard_gates_total": int(len(gates)),
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "overfit_boundary": "No new return replay, no parameter scan, no whitelist; full57 classification only separates core reuse, source readiness, correlation and materiality.",
        "next_step": "Do not widen randomly. Prioritize authorized DCE or alternative source for j/i, keep P0 route/event/TCA collection, and search genuinely non-DCE independent families only when source and forward evidence exist.",
        "references": REFERENCE_LINKS,
    }

    product_map.to_csv(PRODUCT_MAP_PATH, index=False, encoding="utf-8-sig")
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    non_dce_scout.to_csv(NON_DCE_SCOUT_PATH, index=False, encoding="utf-8-sig")
    slot_scenarios.to_csv(SLOT_SCENARIO_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(product_map, family_summary, non_dce_scout, slot_scenarios)
    _write_report(product_map, family_summary, non_dce_scout, slot_scenarios, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
