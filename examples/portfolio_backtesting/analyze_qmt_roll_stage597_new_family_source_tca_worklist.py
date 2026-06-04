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


MODEL_TAG = "stage597_new_family_source_tca_worklist_v1"
OUTPUT_PREFIX = "qmt_roll_stage597_new_family_source_tca_worklist"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE596_PRODUCT_TIERS = OUTPUT_DIR / "qmt_roll_stage596_breadth_risk_slot_design_product_tiers_stage596_breadth_risk_slot_design_v1.csv"
STAGE596_RISK_SLOT_PLAN = OUTPUT_DIR / "qmt_roll_stage596_breadth_risk_slot_design_risk_slot_plan_stage596_breadth_risk_slot_design_v1.csv"
STAGE596_GATES = OUTPUT_DIR / "qmt_roll_stage596_breadth_risk_slot_design_gates_stage596_breadth_risk_slot_design_v1.csv"
STAGE548_SOURCE_MATRIX = OUTPUT_DIR / "qmt_roll_stage548_external_source_alternative_probe_product_source_matrix_stage548_external_source_alternative_probe_v1.csv"
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / "qmt_roll_stage571_external_selector_source_priority_audit_source_priority_stage571_external_selector_source_priority_audit_v1.csv"
STAGE571_FEATURE_PRIOR = OUTPUT_DIR / "qmt_roll_stage571_external_selector_source_priority_audit_feature_prior_stage571_external_selector_source_priority_audit_v1.csv"
STAGE583_TCA_GATES = OUTPUT_DIR / "qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_gates_stage583_stage526_live_tca_evidence_gap_audit_v1.csv"

FAMILY_WORKLIST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_worklist_{MODEL_TAG}.csv"
PRODUCT_WORKLIST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_worklist_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_PRODUCTS = {"y.DCE", "c.DCE", "v.DCE", "lu.INE", "ao.SHFE"}
MAX_CORE_CORR_WATCH = 0.10
TARGET_EFFECTIVE_RISK_SLOTS = 7
TARGET_FAMILIES = 6
TARGET_MAX_SLOT_RISK_PCT = 15.0
MIN_FORWARD_DATES = 20
MIN_FORWARD_RUNS = 20
MIN_TCA_PER_NEW_PRODUCT = 3
MIN_NEW_FAMILY_COUNT_PREFERRED = 3
MIN_NEW_FAMILY_MATERIAL_PNL = 50_000.0

REFERENCE_LINKS = [
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
    "Optimal Allocation of Trend Following Strategies: https://arxiv.org/abs/1410.8409",
    "Trend-following trading strategies in commodity futures: https://www.sciencedirect.com/science/article/pii/S037842660900199X",
    "Riskfolio-Lib: https://github.com/dcajasn/Riskfolio-Lib",
    "skfolio: https://github.com/skfolio/skfolio",
]


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


def _boolish(frame: pd.DataFrame, column: str) -> pd.Series:
    return _num(frame, column).gt(0).astype(int)


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


def _gate_actual(frame: pd.DataFrame, gate: str, default: str = "") -> str:
    if "gate" not in frame.columns or "actual" not in frame.columns:
        return default
    rows = frame[frame["gate"].astype(str).eq(gate)]
    if rows.empty:
        return default
    return str(rows["actual"].iloc[0])


def _load_product_frame() -> pd.DataFrame:
    product_tiers = _read_csv(STAGE596_PRODUCT_TIERS)
    source = _read_csv(STAGE548_SOURCE_MATRIX)
    source_cols = [
        "product_vt_symbol",
        "basis_hist_ready",
        "basis_coverage_rate_pct",
        "basis_months",
        "inventory_recent_ready",
        "inventory_em_rows",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "all_core_external_state_ready",
    ]
    frame = product_tiers.merge(source[[col for col in source_cols if col in source.columns]], on="product_vt_symbol", how="left")
    for column in [
        "total_pnl",
        "positive_year_rate_pct",
        "abs_core_daily_pnl_corr",
        "single_max_order_volume_to_day_volume_pct",
        "single_hard_volume_stress_event_rate_pct",
        "single_volume_data_coverage_rate_pct",
        "basis_coverage_rate_pct",
        "basis_months",
        "inventory_em_rows",
    ]:
        frame[column] = _num(frame, column)
    for column in [
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "all_core_external_state_ready",
    ]:
        frame[column] = _boolish(frame, column)

    source_components = [
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
    ]
    frame["source_component_count"] = frame[source_components].sum(axis=1).astype(int)
    frame["source_component_pct"] = frame["source_component_count"] / len(source_components) * 100.0
    frame["low_core_corr_pass"] = frame["abs_core_daily_pnl_corr"].le(MAX_CORE_CORR_WATCH).astype(int)
    frame["positive_material_hint"] = frame["total_pnl"].gt(0).astype(int)
    frame["capacity_pass_hint"] = (
        frame["capacity_quality_flag"].astype(str).isin(["green", "yellow"])
        & frame["single_hard_volume_stress_event_rate_pct"].le(0)
        & frame["single_max_order_volume_to_day_volume_pct"].le(0.05)
    ).astype(int)
    frame["p0_family"] = frame["product_vt_symbol"].astype(str).isin(P0_PRODUCTS).astype(int)
    return frame


def _product_action(row: pd.Series) -> tuple[str, str, str]:
    product = str(row["product_vt_symbol"])
    family = str(row["product_family"])
    tier = str(row["tier"])
    if tier == "P0_forward_watch":
        gaps: list[str] = []
        if float(row.get("same_family_tiebreak_required", 0)) >= 1:
            gaps.append("同族同向 top1-only")
        if float(row.get("two_route_ready", 0)) < 1:
            gaps.append("补 basis/替代route")
        if float(row.get("event_ready", 0)) < 1:
            gaps.append("补事件/舆情账本")
        if int(row.get("official_monitor_ready", 0)) < 1 and product in {"v.DCE", "ao.SHFE", "lu.INE"}:
            gaps.append("补官方endpoint自动monitor")
        if float(row.get("abs_core_daily_pnl_corr", 0)) > MAX_CORE_CORR_WATCH:
            gaps.append("核心相关观察，不得加权")
        return "P0继续补证", "；".join(gaps) if gaps else "继续forward collection", "P0不是交易白名单，仍需source/TCA闭环"
    if tier == "P1_new_family_candidate":
        return (
            "P1新产品族补证",
            "20个received_at日期；固定事件route；每品种3个真实TCA；同族只算1个风险槽",
            "可增加独立风险槽，但当前只能做source/TCA工作流",
        )
    if tier == "P1_same_family_depth_only":
        return (
            "同族深度观察",
            "只做替补/同族tie-break证据，不计新增独立风险槽",
            "能提升同族选择深度，但不能降低组合单槽风险",
        )
    if tier == "Reject_core_corr_watch":
        return (
            "暂停风险槽",
            f"核心相关 {float(row['abs_core_daily_pnl_corr']):.4f} 超过 {MAX_CORE_CORR_WATCH:.2f}",
            "有收益也不能当独立分散来源",
        )
    if tier == "Reject_capacity_or_liquidity":
        return (
            "暂停风险槽",
            "容量/流动性或年度稳定性不过关",
            "低单笔风险不能靠低流动性品种实现",
        )
    if int(row.get("any_live_external_state", 0)) and float(row.get("total_pnl", 0)) <= 0:
        return (
            "保留数据源观察",
            "source存在但历史机会不足，先不补TCA",
            "有源不等于有alpha，避免因数据可得而过拟合",
        )
    return "观察", "不进入当前扩池工作流", "缺少独立风险槽、材料性或可执行证据"


def _build_product_worklist(product_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    keep_tiers = {
        "P0_forward_watch",
        "P1_new_family_candidate",
        "P1_same_family_depth_only",
        "Reject_core_corr_watch",
        "Reject_capacity_or_liquidity",
        "Reject_no_material_opportunity",
    }
    frame = product_frame[product_frame["tier"].isin(keep_tiers)].copy()
    for _, row in frame.iterrows():
        priority, action, reason = _product_action(row)
        rows.append(
            {
                "product_vt_symbol": row["product_vt_symbol"],
                "product_family": row["product_family"],
                "tier": row["tier"],
                "priority": priority,
                "action": action,
                "reason": reason,
                "total_pnl": float(row["total_pnl"]),
                "positive_year_rate_pct": float(row["positive_year_rate_pct"]),
                "abs_core_daily_pnl_corr": float(row["abs_core_daily_pnl_corr"]),
                "capacity_quality_flag": row["capacity_quality_flag"],
                "capacity_pass_hint": int(row["capacity_pass_hint"]),
                "basis_hist_ready": int(row["basis_hist_ready"]),
                "inventory_recent_ready": int(row["inventory_recent_ready"]),
                "member_detail_live_ready": int(row["member_detail_live_ready"]),
                "exchange_warehouse_live_ready": int(row["exchange_warehouse_live_ready"]),
                "any_live_external_state": int(row["any_live_external_state"]),
                "source_component_count": int(row["source_component_count"]),
                "source_component_pct": float(row["source_component_pct"]),
                "whitelist_allowed": 0,
            }
        )
    order = {
        "P0继续补证": 0,
        "P1新产品族补证": 1,
        "同族深度观察": 2,
        "暂停风险槽": 3,
        "保留数据源观察": 4,
        "观察": 5,
    }
    result = pd.DataFrame(rows)
    result["priority_rank"] = result["priority"].map(order).fillna(99)
    return result.sort_values(["priority_rank", "total_pnl"], ascending=[True, False]).reset_index(drop=True)


def _family_status(row: pd.Series) -> tuple[str, str]:
    if int(row["p0_product_count"]) > 0:
        return "P0_existing_family", "已有P0风险槽，但仍需route/event/official/TCA补证"
    if int(row["p1_new_products"]) > 0:
        return "P1_new_family_worklist", "当前唯一可补的新产品族；只能补source/TCA，不能进白名单"
    if float(row["family_max_abs_core_corr"]) > MAX_CORE_CORR_WATCH and float(row["family_positive_pnl_sum"]) > 0:
        return "Reject_high_core_corr", "有收益但核心相关过高，不适合作为独立风险槽"
    if int(row["source_live_products"]) > 0 and float(row["family_positive_pnl_sum"]) <= 0:
        return "Source_ready_no_materiality", "数据源可得但机会不足，暂不投入TCA"
    if int(row["capacity_pass_products"]) == 0:
        return "Reject_capacity", "容量/流动性不足，不能降低真实单笔风险"
    return "Observe_only", "缺少材料性、低相关或source/TCA闭环"


def _build_family_worklist(product_frame: pd.DataFrame) -> pd.DataFrame:
    family = (
        product_frame.groupby("product_family", as_index=False)
        .agg(
            products=("product_vt_symbol", "count"),
            product_list=("product_vt_symbol", lambda values: ",".join(sorted(map(str, values)))),
            p0_product_count=("p0_family", "sum"),
            p1_new_products=("tier", lambda values: int((values.astype(str) == "P1_new_family_candidate").sum())),
            same_family_depth_products=("tier", lambda values: int((values.astype(str) == "P1_same_family_depth_only").sum())),
            family_total_pnl=("total_pnl", "sum"),
            family_positive_pnl_sum=("total_pnl", lambda values: float(values[values > 0].sum())),
            family_max_abs_core_corr=("abs_core_daily_pnl_corr", "max"),
            family_min_abs_core_corr=("abs_core_daily_pnl_corr", "min"),
            capacity_pass_products=("capacity_pass_hint", "sum"),
            source_live_products=("any_live_external_state", "sum"),
            basis_ready_products=("basis_hist_ready", "sum"),
            inventory_ready_products=("inventory_recent_ready", "sum"),
            member_ready_products=("member_detail_live_ready", "sum"),
            warehouse_ready_products=("exchange_warehouse_live_ready", "sum"),
            avg_source_component_pct=("source_component_pct", "mean"),
        )
    )
    statuses = family.apply(_family_status, axis=1, result_type="expand")
    family["family_status"] = statuses[0]
    family["worklist_reason"] = statuses[1]
    status_rank = {
        "P0_existing_family": 0,
        "P1_new_family_worklist": 1,
        "Reject_high_core_corr": 2,
        "Source_ready_no_materiality": 3,
        "Reject_capacity": 4,
        "Observe_only": 5,
    }
    family["status_rank"] = family["family_status"].map(status_rank).fillna(99)
    return family.sort_values(["status_rank", "family_positive_pnl_sum"], ascending=[True, False]).reset_index(drop=True)


def _build_gates(product_frame: pd.DataFrame, family_worklist: pd.DataFrame) -> pd.DataFrame:
    risk_slot_plan = _read_csv(STAGE596_RISK_SLOT_PLAN)
    stage596_gates = _read_csv(STAGE596_GATES)
    source_priority = _read_csv(STAGE571_SOURCE_PRIORITY)
    feature_prior = _read_csv(STAGE571_FEATURE_PRIOR)
    tca_gates = _read_csv(STAGE583_TCA_GATES)

    p0_family_count = int(product_frame.loc[product_frame["p0_family"].eq(1), "product_family"].nunique())
    p1_new = product_frame[product_frame["tier"].eq("P1_new_family_candidate")].copy()
    p1_new_family_count = int(p1_new["product_family"].nunique())
    effective_slots_after_p1 = p0_family_count + p1_new_family_count
    black = product_frame[product_frame["product_family"].astype(str).eq("black_ferrous")].copy()
    black_p1 = black[black["tier"].eq("P1_new_family_candidate")]
    black_total_positive_pnl = float(black_p1["total_pnl"].clip(lower=0).sum())
    black_products = int(len(black_p1))
    black_source_core_ready = int(
        (
            black_p1["basis_hist_ready"].eq(1)
            & black_p1["inventory_recent_ready"].eq(1)
            & black_p1["any_live_external_state"].eq(1)
        ).sum()
    )
    black_member_warehouse_ready = int(
        (
            black_p1["member_detail_live_ready"].eq(1)
            & black_p1["exchange_warehouse_live_ready"].eq(1)
        ).sum()
    )
    forward_runs = int(pd.to_numeric(source_priority.get("qualified_forward_runs", pd.Series([0])), errors="coerce").max())
    forward_dates = int(pd.to_numeric(source_priority.get("qualified_forward_dates", pd.Series([0])), errors="coerce").max())
    alpha_allowed = int(pd.to_numeric(feature_prior.get("allowed_as_alpha_now", pd.Series([0])), errors="coerce").fillna(0).sum())
    valid_tca_actual = _gate_actual(tca_gates, "valid_live_tca_samples_complete", "0/9 valid P0 samples")
    p0_effective_actual = risk_slot_plan.loc[
        risk_slot_plan["scenario"].astype(str).eq("P0 effective risk slots after y/c top1"),
        "products_or_slots",
    ]
    p0_effective_slots = int(p0_effective_actual.iloc[0]) if not p0_effective_actual.empty else p0_family_count
    high_corr_positive = product_frame[
        product_frame["p0_family"].eq(0)
        & product_frame["total_pnl"].gt(0)
        & product_frame["abs_core_daily_pnl_corr"].gt(MAX_CORE_CORR_WATCH)
    ]

    rows = [
        {
            "gate": "p0_effective_risk_slots",
            "actual": f"{p0_effective_slots} effective slots",
            "threshold": f">={TARGET_EFFECTIVE_RISK_SLOTS}",
            "passed": int(p0_effective_slots >= TARGET_EFFECTIVE_RISK_SLOTS),
            "hard_gate": 1,
            "judgement": "当前P0不足以把单槽风险压到15%以内。",
        },
        {
            "gate": "effective_slots_after_current_p1",
            "actual": f"{effective_slots_after_p1} slots after current P1 new families",
            "threshold": f">={TARGET_EFFECTIVE_RISK_SLOTS}",
            "passed": int(effective_slots_after_p1 >= TARGET_EFFECTIVE_RISK_SLOTS),
            "hard_gate": 1,
            "judgement": "加入j/i所在黑色族后仍只有5个有效槽。",
        },
        {
            "gate": "new_family_count_preferred",
            "actual": f"{p1_new_family_count} new families",
            "threshold": f">={MIN_NEW_FAMILY_COUNT_PREFERRED}",
            "passed": int(p1_new_family_count >= MIN_NEW_FAMILY_COUNT_PREFERRED),
            "hard_gate": 0,
            "judgement": "只找到一个新族，离扩池目标仍远。",
        },
        {
            "gate": "black_ferrous_low_core_corr",
            "actual": f"max abs core corr={black_p1['abs_core_daily_pnl_corr'].max():.4f}" if black_products else "0 products",
            "threshold": f"<={MAX_CORE_CORR_WATCH:.2f}",
            "passed": int(black_products > 0 and black_p1["abs_core_daily_pnl_corr"].max() <= MAX_CORE_CORR_WATCH),
            "hard_gate": 1,
            "judgement": "j/i低核心相关通过，是当前最值得补证的新族。",
        },
        {
            "gate": "black_ferrous_materiality",
            "actual": f"positive P1 family pnl={black_total_positive_pnl:.2f}",
            "threshold": f">={MIN_NEW_FAMILY_MATERIAL_PNL:.0f}",
            "passed": int(black_total_positive_pnl >= MIN_NEW_FAMILY_MATERIAL_PNL),
            "hard_gate": 1,
            "judgement": "历史机会偏小，不能直接当材料性收益源。",
        },
        {
            "gate": "black_ferrous_core_source_ready",
            "actual": f"{black_source_core_ready}/{black_products} basis+inventory+live_state ready",
            "threshold": f"{black_products}/{black_products}",
            "passed": int(black_products > 0 and black_source_core_ready == black_products),
            "hard_gate": 0,
            "judgement": "核心供需源可补，但只是source可得，不等于alpha可得。",
        },
        {
            "gate": "black_ferrous_member_warehouse_ready",
            "actual": f"{black_member_warehouse_ready}/{black_products} member+warehouse ready",
            "threshold": f"{black_products}/{black_products}",
            "passed": int(black_products > 0 and black_member_warehouse_ready == black_products),
            "hard_gate": 0,
            "judgement": "DCE会员/仓单侧仍缺，不能当完整外生闭环。",
        },
        {
            "gate": "new_family_live_tca_samples",
            "actual": "0/6 inferred valid samples",
            "threshold": f">={black_products * MIN_TCA_PER_NEW_PRODUCT}",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "j/i每品种至少3个真实TCA样本前不得paper。",
        },
        {
            "gate": "source_alpha_allowed_now",
            "actual": f"{alpha_allowed} features/routes allowed as alpha",
            "threshold": ">=1 after 20-date PIT audit",
            "passed": int(alpha_allowed >= 1),
            "hard_gate": 1,
            "judgement": "当前source只能forward monitor，不能历史回填当selector。",
        },
        {
            "gate": "forward_sample_depth",
            "actual": f"runs={forward_runs}, dates={forward_dates}",
            "threshold": f"runs>={MIN_FORWARD_RUNS}, dates>={MIN_FORWARD_DATES}",
            "passed": int(forward_runs >= MIN_FORWARD_RUNS and forward_dates >= MIN_FORWARD_DATES),
            "hard_gate": 1,
            "judgement": "样本深度不足，禁止收益回测selector。",
        },
        {
            "gate": "p0_live_tca_gap",
            "actual": valid_tca_actual,
            "threshold": "P0先达到9个有效样本；新族再补每品种3个",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "基础候选本身真实成交无偏差还没关账。",
        },
        {
            "gate": "non_p0_high_core_corr_rejected",
            "actual": ",".join(high_corr_positive["product_vt_symbol"].astype(str).tolist()) or "none",
            "threshold": "positive products over corr watch cannot be risk slots",
            "passed": int(len(high_corr_positive) > 0),
            "hard_gate": 0,
            "judgement": "br.SHFE有收益也必须先排除为新增独立槽，避免伪分散。",
        },
        {
            "gate": "no_whitelist_or_ab",
            "actual": "promotion=false,paper=false,trading=false",
            "threshold": "must remain false",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "本阶段只是工作清单，不生成交易候选。",
        },
        {
            "gate": "stage596_pairwise_corr_context",
            "actual": _gate_actual(stage596_gates, "pairwise_corr_budget", "P0 pairwise corr passed"),
            "threshold": "context only",
            "passed": 1,
            "hard_gate": 0,
            "judgement": "相关性不是P0主要矛盾，但新增品种仍要避开核心相关。",
        },
    ]
    return pd.DataFrame(rows)


def _build_next_actions(product_worklist: pd.DataFrame, family_worklist: pd.DataFrame) -> pd.DataFrame:
    black_products = product_worklist[
        product_worklist["product_family"].astype(str).eq("black_ferrous")
        & product_worklist["tier"].astype(str).eq("P1_new_family_candidate")
    ]["product_vt_symbol"].astype(str).tolist()
    rows = [
        {
            "priority": 1,
            "scope": "black_ferrous",
            "targets": ",".join(black_products) or "j.DCE,i.DCE",
            "action": "新建P1 forward source账本：basis/inventory/事件route，每日只计一次received_at，累计20日。",
            "stop_condition": "20日后若固定IC/bucket仍不能提高3/6个月holding体验，停止。",
        },
        {
            "priority": 2,
            "scope": "black_ferrous_tca",
            "targets": ",".join(black_products) or "j.DCE,i.DCE",
            "action": "每品种至少3个真实或独立分钟证据TCA样本，记录signal/window/submit/fill/VWAP/participation。",
            "stop_condition": "任一品种出现容量/成交偏差硬失败，则不进paper。",
        },
        {
            "priority": 3,
            "scope": "P0",
            "targets": "y.DCE,c.DCE,v.DCE,lu.INE,ao.SHFE",
            "action": "继续P0 route/event/official endpoint/TCA补证；y/c执行同族同向top1-only。",
            "stop_condition": "P0未达20日forward与9个TCA样本前，不启动宽池收益回测。",
        },
        {
            "priority": 4,
            "scope": "reject_high_corr",
            "targets": ",".join(
                product_worklist[
                    product_worklist["tier"].astype(str).eq("Reject_core_corr_watch")
                    & product_worklist["total_pnl"].gt(0)
                ]["product_vt_symbol"].astype(str).tolist()
            )
            or "br.SHFE",
            "action": "只做观察，不作为独立风险槽；若未来核心相关降到0.10以下再重审。",
            "stop_condition": "核心相关长期高于0.10则停止。",
        },
        {
            "priority": 5,
            "scope": "source_ready_no_materiality",
            "targets": ",".join(
                family_worklist[
                    family_worklist["family_status"].astype(str).eq("Source_ready_no_materiality")
                ]["product_family"].astype(str).tolist()
            )
            or "soft_agri,precious_metals",
            "action": "有数据源但历史机会不足的族先不投入TCA，只保留低频监控。",
            "stop_condition": "没有新的事前selector证据则不进入回测。",
        },
    ]
    return pd.DataFrame(rows)


def _build_decision(family_worklist: pd.DataFrame, product_worklist: pd.DataFrame, gates: pd.DataFrame) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    p1_new = product_worklist[product_worklist["tier"].astype(str).eq("P1_new_family_candidate")]
    p0_families = int(family_worklist.loc[family_worklist["p0_product_count"].gt(0), "product_family"].nunique())
    p1_new_families = int(p1_new["product_family"].nunique())
    effective_slots = p0_families + p1_new_families
    black_positive_pnl = float(p1_new.loc[p1_new["product_family"].astype(str).eq("black_ferrous"), "total_pnl"].clip(lower=0).sum())
    return {
        "stage": "Stage297",
        "script_stage": "Stage597",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "new_family_worklist_black_ferrous_only_no_paper",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "p0_effective_family_slots": p0_families,
        "p1_new_family_count": p1_new_families,
        "effective_slots_with_current_p1": effective_slots,
        "target_effective_risk_slots": TARGET_EFFECTIVE_RISK_SLOTS,
        "target_families": TARGET_FAMILIES,
        "black_ferrous_p1_products": int(len(p1_new[p1_new["product_family"].astype(str).eq("black_ferrous")])),
        "black_ferrous_positive_pnl": black_positive_pnl,
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "main_judgement": (
            "减少单笔风险、扩大品种池是正确方向，但现有证据只支持把j/i黑色族放入source/TCA补证清单；"
            "不能直接收益回测、paper或交易白名单。"
        ),
        "overfit_boundary": "No strategy replay, no return optimization, no new whitelist; this is a source/capacity/correlation/TCA worklist.",
        "next_step": "Accumulate 20-date point-in-time ledgers and 3 TCA samples per P1 product before any fixed low-risk sleeve test.",
    }


def _plot(family_worklist: pd.DataFrame, product_worklist: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle("Stage597 new-family source/TCA worklist", fontsize=16)

    ax = axes[0, 0]
    colors = {
        "P0_existing_family": "#1f77b4",
        "P1_new_family_worklist": "#2ca02c",
        "Reject_high_core_corr": "#d62728",
        "Source_ready_no_materiality": "#ffbf00",
        "Reject_capacity": "#7f7f7f",
        "Observe_only": "#ff7f0e",
    }
    for status, group in family_worklist.groupby("family_status", sort=False):
        ax.scatter(
            group["family_max_abs_core_corr"],
            group["family_positive_pnl_sum"],
            s=np.clip(group["products"].astype(float) * 80, 80, 500),
            alpha=0.78,
            color=colors.get(status, "#9467bd"),
            label=status,
            edgecolor="black",
            linewidth=0.4,
        )
        for _, row in group.iterrows():
            should_label = (
                float(row["family_positive_pnl_sum"]) >= 10_000
                or str(row["family_status"]) in {"P1_new_family_worklist", "Reject_high_core_corr"}
            )
            if should_label:
                ax.annotate(str(row["product_family"]), (row["family_max_abs_core_corr"], row["family_positive_pnl_sum"]), fontsize=8)
    ax.axvline(MAX_CORE_CORR_WATCH, color="red", linestyle="--", linewidth=1)
    ax.axhline(MIN_NEW_FAMILY_MATERIAL_PNL, color="green", linestyle="--", linewidth=1)
    ax.set_title("Family opportunity vs core correlation")
    ax.set_xlabel("max abs core daily PnL corr")
    ax.set_ylabel("positive PnL sum")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    source_view = product_worklist[
        product_worklist["priority"].isin(["P0继续补证", "P1新产品族补证", "暂停风险槽", "保留数据源观察"])
    ].head(16)
    source_cols = [
        "basis_hist_ready",
        "inventory_recent_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "any_live_external_state",
        "capacity_pass_hint",
    ]
    heat = source_view.set_index("product_vt_symbol")[source_cols].astype(float)
    im = ax.imshow(heat.values, vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(source_cols)))
    ax.set_xticklabels(source_cols, rotation=25, ha="right")
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(heat.index)
    ax.set_title("Source/capacity readiness by product")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, int(heat.values[i, j]), ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    slot_labels = ["P0 effective", "+ black_ferrous", "target"]
    p0_effective = int(family_worklist["p0_product_count"].gt(0).sum())
    p1_families = int(
        product_worklist[product_worklist["tier"].astype(str).eq("P1_new_family_candidate")]["product_family"].nunique()
    )
    slot_values = [p0_effective, p0_effective + p1_families, TARGET_EFFECTIVE_RISK_SLOTS]
    slot_risks = [100.0 / value for value in slot_values]
    bars = ax.bar(slot_labels, slot_risks, color=["#d62728", "#ffbf00", "#2ca02c"])
    ax.axhline(TARGET_MAX_SLOT_RISK_PCT, color="green", linestyle="--", label="15% target")
    ax.set_title("Risk per effective slot")
    ax.set_ylabel("risk per slot (%)")
    ax.legend(fontsize=8)
    for bar, slots, risk in zip(bars, slot_values, slot_risks):
        ax.text(bar.get_x() + bar.get_width() / 2, risk + 0.7, f"{risk:.1f}%\n{slots} slots", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    gate_view = gates.copy()
    gate_view["passed"] = gate_view["passed"].astype(int)
    colors_gate = np.where(gate_view["passed"].eq(1), "#2ca02c", "#d62728")
    ax.barh(gate_view["gate"], np.ones(len(gate_view)), color=colors_gate, alpha=0.88)
    for idx, passed in enumerate(gate_view["passed"]):
        ax.text(0.5, idx, "PASS" if passed else "FAIL", va="center", ha="center", color="white", fontsize=8, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_title("Gates: worklist only, no paper")
    ax.set_xlabel("status")
    ax.set_xticks([])
    ax.grid(axis="x", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _build_report(
    decision: dict[str, Any],
    family_worklist: pd.DataFrame,
    product_worklist: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
) -> str:
    return f"""# Stage597 新产品族 source/TCA 工作清单

- 生成时间：`{decision["generated_at_local"]}`
- 决策：`{decision["decision"]}`
- 阶段性质：只读归因/工作清单；不做收益回测，不改策略，不生成交易白名单。
- 调研参考：
{chr(10).join(f"  - {item}" for item in REFERENCE_LINKS)}

## 回答用户问题

- “减少单笔风险、扩大品种池、每年抓部分品种趋势、避免高相关风险”方向成立，但必须按有效风险槽执行，而不是按品种数量执行。
- 当前 P0 有效风险槽约 `4` 个；加入当前唯一可接受的新产品族 `black_ferrous(j/i)` 后也只有 `5` 个，离 `>=7` 个有效槽和单槽风险 `<=15%` 还差至少 `2` 个独立产品族。
- `j.DCE/i.DCE` 的优势是核心相关低、容量过线、basis/inventory 有源；弱点是同属一个黑色族、历史材料性只有 `{decision["black_ferrous_positive_pnl"]:.2f}`、DCE 会员/仓单闭环不足、真实TCA为0。
- `br.SHFE` 有收益但核心相关过高，不能拿来当独立分散；`soft_agri/precious_metals` 等有些源可得但机会不足，先不投入TCA。

## Family Worklist

{_md_table(family_worklist, [
    "product_family",
    "family_status",
    "products",
    "product_list",
    "p0_product_count",
    "p1_new_products",
    "family_positive_pnl_sum",
    "family_max_abs_core_corr",
    "capacity_pass_products",
    "source_live_products",
    "basis_ready_products",
    "inventory_ready_products",
    "member_ready_products",
    "warehouse_ready_products",
    "worklist_reason",
], max_rows=20)}

## Product Worklist

{_md_table(product_worklist, [
    "product_vt_symbol",
    "product_family",
    "tier",
    "priority",
    "action",
    "reason",
    "total_pnl",
    "positive_year_rate_pct",
    "abs_core_daily_pnl_corr",
    "capacity_quality_flag",
    "source_component_count",
    "whitelist_allowed",
], max_rows=28)}

## Gates

{_md_table(gates)}

## Next Actions

{_md_table(next_actions)}

## 输出

- family worklist：`{FAMILY_WORKLIST_PATH}`
- product worklist：`{PRODUCT_WORKLIST_PATH}`
- gates：`{GATES_PATH}`
- next actions：`{NEXT_ACTIONS_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""


def main() -> None:
    product_frame = _load_product_frame()
    family_worklist = _build_family_worklist(product_frame)
    product_worklist = _build_product_worklist(product_frame)
    gates = _build_gates(product_frame, family_worklist)
    next_actions = _build_next_actions(product_worklist, family_worklist)
    decision = _build_decision(family_worklist, product_worklist, gates)
    report = _build_report(decision, family_worklist, product_worklist, gates, next_actions)

    family_worklist.to_csv(FAMILY_WORKLIST_PATH, index=False, encoding="utf-8-sig")
    product_worklist.to_csv(PRODUCT_WORKLIST_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _plot(family_worklist, product_worklist, gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
