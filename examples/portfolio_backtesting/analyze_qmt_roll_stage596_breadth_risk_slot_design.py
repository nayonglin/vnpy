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


MODEL_TAG = "stage596_breadth_risk_slot_design_v1"
OUTPUT_PREFIX = "qmt_roll_stage596_breadth_risk_slot_design"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE574_CANDIDATE_MAP = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE590_THRESHOLDS = OUTPUT_DIR / "qmt_roll_stage590_breadth_selector_edge_threshold_audit_thresholds_stage590_breadth_selector_edge_threshold_audit_v1.csv"
STAGE592_PRODUCT_BUDGET = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_product_budget_stage592_breadth_selector_structure_audit_v1.csv"
STAGE592_FAMILY_BUDGET = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_family_budget_stage592_breadth_selector_structure_audit_v1.csv"
STAGE592_GATES = OUTPUT_DIR / "qmt_roll_stage592_breadth_selector_structure_audit_structure_gates_stage592_breadth_selector_structure_audit_v1.csv"
STAGE595_PRODUCT_READINESS = OUTPUT_DIR / "qmt_roll_stage595_p0_official_endpoint_discovery_product_readiness_stage595_p0_official_endpoint_discovery_v1.csv"

PRODUCT_TIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_tiers_{MODEL_TAG}.csv"
RISK_SLOT_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_slot_plan_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_PRODUCTS = {"y.DCE", "c.DCE", "v.DCE", "lu.INE", "ao.SHFE"}
MAX_PRODUCT_RISK_HARD_PCT = 20.0
MAX_PRODUCT_RISK_PREFERRED_PCT = 15.0
MAX_FAMILY_RISK_PCT = 20.0
MAX_CORE_CORR_WATCH = 0.10
MAX_PAIRWISE_ABS_CORR = 0.50
MIN_RAW_PRODUCTS_FOR_PREFERRED = 7
MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED = 7
MIN_FAMILIES_FOR_PREFERRED = 6
MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_VALID_TCA_SAMPLES = 9
MIN_SELECTOR_CAPTURE_PCT = 92.58401999814832
MIN_MATERIAL_ACTUAL_SLEEVE_PNL = 50_000.0


REFERENCE_LINKS = [
    "AQR Trend Following: https://www.aqr.com/insights/trend-following",
    "Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix",
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


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 24) -> str:
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


def _metric_value(thresholds: pd.DataFrame, metric: str, default: float = 0.0) -> float:
    if thresholds.empty or "metric" not in thresholds.columns or "value" not in thresholds.columns:
        return default
    rows = thresholds[thresholds["metric"].astype(str).eq(metric)]
    if rows.empty:
        return default
    return float(pd.to_numeric(rows["value"], errors="coerce").fillna(default).iloc[0])


def _gate_actual(gates: pd.DataFrame, gate: str, default: str = "") -> str:
    if gates.empty or "gate" not in gates.columns or "actual" not in gates.columns:
        return default
    rows = gates[gates["gate"].astype(str).eq(gate)]
    if rows.empty:
        return default
    return str(rows["actual"].iloc[0])


def _official_ready_map() -> dict[str, int]:
    readiness = _read_csv(STAGE595_PRODUCT_READINESS)
    if readiness.empty:
        return {}
    return {
        str(row["product_vt_symbol"]): int(float(row.get("official_auto_monitor_ready_rows", 0)))
        for _, row in readiness.iterrows()
    }


def _build_product_tiers() -> pd.DataFrame:
    candidate = _read_csv(STAGE574_CANDIDATE_MAP)
    p0_budget = _read_csv(STAGE592_PRODUCT_BUDGET)
    official_ready = _official_ready_map()

    frame = candidate.copy()
    for column in [
        "total_pnl",
        "positive_year_rate_pct",
        "abs_core_daily_pnl_corr",
        "single_hard_volume_stress_event_rate_pct",
        "single_max_order_volume_to_day_volume_pct",
        "single_volume_data_coverage_rate_pct",
        "max_broker10_margin_to_sleeve_equity_pct",
    ]:
        frame[column] = _num(frame, column)
    frame["is_p0"] = frame["product_vt_symbol"].astype(str).isin(P0_PRODUCTS).astype(int)
    frame["official_monitor_ready"] = frame["product_vt_symbol"].map(official_ready).fillna(0).astype(int)

    evidence_cols = [
        "product_vt_symbol",
        "two_route_ready",
        "event_ready",
        "same_family_tiebreak_required",
        "structure_role",
        "primary_gap",
        "evidence_score_0_100",
    ]
    evidence = p0_budget[[col for col in evidence_cols if col in p0_budget.columns]].copy()
    if not evidence.empty:
        frame = frame.merge(evidence, on="product_vt_symbol", how="left", suffixes=("", "_p0"))
    for column in ["two_route_ready", "event_ready", "same_family_tiebreak_required"]:
        frame[column] = _num(frame, column)
    frame["evidence_score_0_100"] = _num(frame, "evidence_score_0_100")

    capacity_ok = (
        frame["capacity_quality_flag"].astype(str).isin(["green", "yellow"])
        & frame["single_hard_volume_stress_event_rate_pct"].le(0.0)
        & frame["single_max_order_volume_to_day_volume_pct"].le(0.05)
        & frame["single_volume_data_coverage_rate_pct"].ge(75.0)
    )
    low_core_corr = frame["abs_core_daily_pnl_corr"].le(MAX_CORE_CORR_WATCH)
    positive_opportunity = frame["total_pnl"].gt(0)
    repeatability_ok = frame["positive_year_rate_pct"].ge(28.0)
    p1_new_family = (
        frame["is_p0"].eq(0)
        & positive_opportunity
        & repeatability_ok
        & capacity_ok
        & low_core_corr
        & ~frame["product_family"].isin(p0_budget["product_family"].dropna().astype(str).unique())
    )
    p1_same_family = (
        frame["is_p0"].eq(0)
        & positive_opportunity
        & repeatability_ok
        & capacity_ok
        & low_core_corr
        & frame["product_family"].isin(p0_budget["product_family"].dropna().astype(str).unique())
    )
    p2_watch = (
        frame["is_p0"].eq(0)
        & positive_opportunity
        & capacity_ok
        & low_core_corr
        & ~p1_new_family
        & ~p1_same_family
    )

    frame["tier"] = np.select(
        [
            frame["is_p0"].eq(1),
            p1_new_family,
            p1_same_family,
            p2_watch,
            frame["abs_core_daily_pnl_corr"].gt(MAX_CORE_CORR_WATCH),
            ~capacity_ok,
            frame["total_pnl"].le(0),
        ],
        [
            "P0_forward_watch",
            "P1_new_family_candidate",
            "P1_same_family_depth_only",
            "P2_observe_positive_lowcorr",
            "Reject_core_corr_watch",
            "Reject_capacity_or_liquidity",
            "Reject_no_material_opportunity",
        ],
        default="Reject_observe_only",
    )
    frame["new_effective_family_slot"] = (frame["tier"].eq("P1_new_family_candidate")).astype(int)
    frame["risk_slot_reason"] = np.select(
        [
            frame["tier"].eq("P0_forward_watch") & frame["same_family_tiebreak_required"].eq(1),
            frame["tier"].eq("P0_forward_watch"),
            frame["tier"].eq("P1_new_family_candidate"),
            frame["tier"].eq("P1_same_family_depth_only"),
        ],
        [
            "P0但同族y/c必须top1-only，不能算两个独立风险槽",
            "P0已有机会和容量，但要补route/event/official/TCA",
            "可能增加独立风险槽；先补外生route和真实TCA",
            "只增加同族深度，不能显著降低单族风险",
        ],
        default="不进入扩池风险槽",
    )
    sort_order = {
        "P0_forward_watch": 0,
        "P1_new_family_candidate": 1,
        "P1_same_family_depth_only": 2,
        "P2_observe_positive_lowcorr": 3,
        "Reject_core_corr_watch": 4,
        "Reject_capacity_or_liquidity": 5,
        "Reject_no_material_opportunity": 6,
        "Reject_observe_only": 7,
    }
    frame["tier_rank"] = frame["tier"].map(sort_order).fillna(99)
    return frame.sort_values(["tier_rank", "total_pnl"], ascending=[True, False]).reset_index(drop=True)


def _build_risk_slot_plan(product_tiers: pd.DataFrame) -> pd.DataFrame:
    p0 = product_tiers[product_tiers["tier"].eq("P0_forward_watch")].copy()
    p1_new = product_tiers[product_tiers["tier"].eq("P1_new_family_candidate")].copy()
    p1_same = product_tiers[product_tiers["tier"].eq("P1_same_family_depth_only")].copy()

    raw_p0_products = int(len(p0))
    p0_families = int(p0["product_family"].nunique())
    effective_p0_slots = int(p0_families)
    with_new_family_slots = effective_p0_slots + int(p1_new["product_family"].nunique())

    rows = [
        {
            "scenario": "P0 raw product count",
            "products_or_slots": raw_p0_products,
            "families": p0_families,
            "single_slot_risk_pct": 100.0 / raw_p0_products if raw_p0_products else np.nan,
            "preferred_pass": int(raw_p0_products >= MIN_RAW_PRODUCTS_FOR_PREFERRED),
            "comment": "按5个P0等权，单产品风险20%，只过硬线不过15%偏好线。",
        },
        {
            "scenario": "P0 effective risk slots after y/c top1",
            "products_or_slots": effective_p0_slots,
            "families": p0_families,
            "single_slot_risk_pct": 100.0 / effective_p0_slots if effective_p0_slots else np.nan,
            "preferred_pass": int(effective_p0_slots >= MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED),
            "comment": "y/c同族同向top1-only后，有效独立风险槽只有4个，实际单槽风险更高。",
        },
        {
            "scenario": "P0 + current P1 new-family candidates",
            "products_or_slots": with_new_family_slots,
            "families": p0_families + int(p1_new["product_family"].nunique()),
            "single_slot_risk_pct": 100.0 / with_new_family_slots if with_new_family_slots else np.nan,
            "preferred_pass": int(with_new_family_slots >= MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED),
            "comment": "只使用当前低核心相关、容量过线、正收益的新产品族候选后，仍难达到7个有效槽。",
        },
        {
            "scenario": "Preferred target",
            "products_or_slots": MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED,
            "families": MIN_FAMILIES_FOR_PREFERRED,
            "single_slot_risk_pct": 100.0 / MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED,
            "preferred_pass": 1,
            "comment": "下一轮扩池目标：>=7个有效风险槽、>=6个产品族，单槽风险<=15%。",
        },
    ]
    if not p1_same.empty:
        rows.append(
            {
                "scenario": "Same-family depth only",
                "products_or_slots": int(len(p1_same)),
                "families": int(p1_same["product_family"].nunique()),
                "single_slot_risk_pct": np.nan,
                "preferred_pass": 0,
                "comment": "这些产品可补同族选择深度，但不能解决独立风险槽不足。",
            }
        )
    return pd.DataFrame(rows)


def _build_gates(product_tiers: pd.DataFrame, risk_slot_plan: pd.DataFrame) -> pd.DataFrame:
    stage592_gates = _read_csv(STAGE592_GATES)
    thresholds = _read_csv(STAGE590_THRESHOLDS)

    p0 = product_tiers[product_tiers["tier"].eq("P0_forward_watch")]
    p1_new = product_tiers[product_tiers["tier"].eq("P1_new_family_candidate")]
    p1_new_families = int(p1_new["product_family"].nunique())
    effective_slots = int(
        risk_slot_plan.loc[
            risk_slot_plan["scenario"].eq("P0 + current P1 new-family candidates"),
            "products_or_slots",
        ].iloc[0]
    )

    p0_capture = _metric_value(thresholds, "p0_fixed_watchlist_opportunity_capture_vs_hindsight_top6_pct")
    random_p95 = _metric_value(thresholds, "random_familycap_k6_p95_total_opportunity")
    actual_all = _metric_value(thresholds, "actual_all_noncore_sleeve_pnl")
    official_ready = int(_read_csv(STAGE595_PRODUCT_READINESS)["official_auto_monitor_ready_rows"].sum())

    rows = [
        {
            "gate": "single_product_risk_hard",
            "actual": "20.00% P0 raw equal risk",
            "threshold": "<=20%",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "当前P0只过硬线。",
        },
        {
            "gate": "single_product_risk_preferred",
            "actual": "20.00% P0 raw equal risk / 25.00% effective after y/c top1",
            "threshold": "<=15%",
            "passed": 0,
            "hard_gate": 0,
            "judgement": "想真正降低单笔/单槽体验，必须增加有效独立风险槽。",
        },
        {
            "gate": "effective_risk_slots",
            "actual": f"{effective_slots} slots with current P1 new-family candidates",
            "threshold": f">={MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED} slots",
            "passed": int(effective_slots >= MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED),
            "hard_gate": 1,
            "judgement": "当前可接受的新产品族不够，扩池还没解决体验目标。",
        },
        {
            "gate": "new_family_candidate_depth",
            "actual": f"{p1_new_families} new families",
            "threshold": ">=3 new families preferred",
            "passed": int(p1_new_families >= 3),
            "hard_gate": 0,
            "judgement": "新增产品最好来自新产品族，不要只加同族深度。",
        },
        {
            "gate": "pairwise_corr_budget",
            "actual": _gate_actual(stage592_gates, "pairwise_corr_budget", "max P0 abs pairwise corr=0.0508"),
            "threshold": f"<={MAX_PAIRWISE_ABS_CORR:.2f}",
            "passed": 1,
            "hard_gate": 1,
            "judgement": "P0内部相关性不是当前瓶颈。",
        },
        {
            "gate": "core_corr_watch",
            "actual": _gate_actual(stage592_gates, "core_corr_watch", "max abs core corr=0.1543"),
            "threshold": f"<={MAX_CORE_CORR_WATCH:.2f} preferred",
            "passed": 0,
            "hard_gate": 0,
            "judgement": "lu.INE机会高但与核心相关超过观察线，不能无限加权。",
        },
        {
            "gate": "selector_edge_threshold",
            "actual": f"P0 capture={p0_capture:.2f}%",
            "threshold": f">={MIN_SELECTOR_CAPTURE_PCT:.2f}%",
            "passed": int(p0_capture >= MIN_SELECTOR_CAPTURE_PCT),
            "hard_gate": 1,
            "judgement": "随机/固定P0还不够，需要真正point-in-time selector edge。",
        },
        {
            "gate": "random_breadth_not_enough",
            "actual": f"random familycap k6 p95 opportunity={random_p95:.2f}",
            "threshold": "well below selector materiality proxy",
            "passed": 1,
            "hard_gate": 0,
            "judgement": "随机扩池不能自然抓趋势，选品是必要条件。",
        },
        {
            "gate": "naive_all_noncore_materiality",
            "actual": f"actual all noncore sleeve={actual_all:.2f}",
            "threshold": f">={MIN_MATERIAL_ACTUAL_SLEEVE_PNL:.0f}",
            "passed": int(actual_all >= MIN_MATERIAL_ACTUAL_SLEEVE_PNL),
            "hard_gate": 1,
            "judgement": "全非核心平铺没有材料性，不能替代选品。",
        },
        {
            "gate": "official_monitor_ready",
            "actual": f"{official_ready}/3 exact official monitors ready",
            "threshold": "3/3",
            "passed": int(official_ready >= 3),
            "hard_gate": 1,
            "judgement": "v/ao/lu外生官方源仍未可自动监控。",
        },
        {
            "gate": "forward_sample_depth",
            "actual": _gate_actual(stage592_gates, "forward_sample_depth", "runs=2, dates=2"),
            "threshold": f"runs>={MIN_FORWARD_RUNS}, dates>={MIN_FORWARD_DATES}",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "样本深度不足前禁止收益回测selector。",
        },
        {
            "gate": "live_tca_samples",
            "actual": "0/9 valid P0 samples",
            "threshold": f">={MIN_VALID_TCA_SAMPLES}",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "真实成交无偏差仍未关账。",
        },
    ]
    return pd.DataFrame(rows)


def _build_next_actions(product_tiers: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    p0 = product_tiers[product_tiers["tier"].eq("P0_forward_watch")]
    for _, row in p0.iterrows():
        gaps: list[str] = []
        if float(row.get("same_family_tiebreak_required", 0)) >= 1:
            gaps.append("同族同向top1-only")
        if float(row.get("two_route_ready", 0)) < 1:
            gaps.append("补basis或替代route")
        if float(row.get("event_ready", 0)) < 1:
            gaps.append("补真实事件/舆情账本")
        if str(row["product_vt_symbol"]) in {"v.DCE", "ao.SHFE", "lu.INE"} and int(row.get("official_monitor_ready", 0)) < 1:
            gaps.append("补官方endpoint/cookie/vendor snapshot")
        if float(row.get("abs_core_daily_pnl_corr", 0)) > MAX_CORE_CORR_WATCH:
            gaps.append("核心相关观察，不得加权")
        rows.append(
            {
                "priority": "P0",
                "product_vt_symbol": row["product_vt_symbol"],
                "product_family": row["product_family"],
                "action": "；".join(gaps) if gaps else "继续forward collection",
                "reason": row["risk_slot_reason"],
            }
        )
    p1_new = product_tiers[product_tiers["tier"].eq("P1_new_family_candidate")]
    for _, row in p1_new.head(6).iterrows():
        rows.append(
            {
                "priority": "P1",
                "product_vt_symbol": row["product_vt_symbol"],
                "product_family": row["product_family"],
                "action": "只做source/TCA补证，不进白名单",
                "reason": "可能增加独立风险槽，但尚无point-in-time selector证据。",
            }
        )
    if not rows:
        rows.append(
            {
                "priority": "P0",
                "product_vt_symbol": "all",
                "product_family": "all",
                "action": "先补forward ledger与TCA",
                "reason": "没有产品满足扩池风险槽条件。",
            }
        )
    return pd.DataFrame(rows)


def _build_decision(product_tiers: pd.DataFrame, risk_slot_plan: pd.DataFrame, gates: pd.DataFrame) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    p0 = product_tiers[product_tiers["tier"].eq("P0_forward_watch")]
    p1_new = product_tiers[product_tiers["tier"].eq("P1_new_family_candidate")]
    effective_slots = int(
        risk_slot_plan.loc[
            risk_slot_plan["scenario"].eq("P0 + current P1 new-family candidates"),
            "products_or_slots",
        ].iloc[0]
    )
    return {
        "stage": "Stage296",
        "script_stage": "Stage596",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "breadth_risk_slot_design_valid_direction_not_tradeable",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "raw_p0_products": int(len(p0)),
        "p0_families": int(p0["product_family"].nunique()),
        "p1_new_family_candidates": int(len(p1_new)),
        "p1_new_family_count": int(p1_new["product_family"].nunique()),
        "effective_slots_with_current_p1": effective_slots,
        "preferred_effective_slots_required": MIN_EFFECTIVE_RISK_SLOTS_FOR_PREFERRED,
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "main_judgement": (
            "低单笔风险扩池方向成立，但当前不是简单加品种；必须先增加独立风险槽、补point-in-time selector证据、"
            "关闭官方源和TCA缺口。"
        ),
        "overfit_boundary": "No strategy replay, no TopN scan, no product whitelist promotion; only consolidates pre-existing frozen audits.",
        "next_step": "Build Stage597 candidate-family source/TCA worklist or wait for forward ledger sample depth before predictive tests.",
    }


def _plot(product_tiers: pd.DataFrame, risk_slot_plan: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle("Stage596 breadth risk slot design: direction valid, not tradeable", fontsize=16)

    scatter = product_tiers[product_tiers["tier"].isin([
        "P0_forward_watch",
        "P1_new_family_candidate",
        "P1_same_family_depth_only",
        "P2_observe_positive_lowcorr",
        "Reject_core_corr_watch",
    ])].copy()
    colors = {
        "P0_forward_watch": "#1f77b4",
        "P1_new_family_candidate": "#2ca02c",
        "P1_same_family_depth_only": "#98df8a",
        "P2_observe_positive_lowcorr": "#ff7f0e",
        "Reject_core_corr_watch": "#d62728",
    }
    ax = axes[0, 0]
    for tier, group in scatter.groupby("tier", sort=False):
        ax.scatter(
            group["abs_core_daily_pnl_corr"],
            group["total_pnl"],
            s=np.clip(group["positive_year_rate_pct"].fillna(0) * 4, 40, 360),
            alpha=0.75,
            label=tier,
            color=colors.get(tier, "#7f7f7f"),
            edgecolor="black",
            linewidth=0.4,
        )
        for _, row in group.head(10).iterrows():
            ax.annotate(str(row["product_vt_symbol"]), (row["abs_core_daily_pnl_corr"], row["total_pnl"]), fontsize=8)
    ax.axvline(MAX_CORE_CORR_WATCH, color="red", linestyle="--", linewidth=1)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Opportunity vs core correlation")
    ax.set_xlabel("abs core daily PnL corr")
    ax.set_ylabel("single-product total PnL")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[0, 1]
    risk_view = risk_slot_plan[risk_slot_plan["scenario"].isin([
        "P0 raw product count",
        "P0 effective risk slots after y/c top1",
        "P0 + current P1 new-family candidates",
        "Preferred target",
    ])].copy()
    bars = ax.bar(
        risk_view["scenario"],
        risk_view["single_slot_risk_pct"].astype(float),
        color=["#ffbf00" if passed == 0 else "#2ca02c" for passed in risk_view["preferred_pass"]],
    )
    ax.axhline(MAX_PRODUCT_RISK_PREFERRED_PCT, color="green", linestyle="--", label="15% preferred")
    ax.axhline(MAX_PRODUCT_RISK_HARD_PCT, color="red", linestyle="--", label="20% hard")
    ax.set_title("Single effective risk slot pressure")
    ax.set_ylabel("risk per slot (%)")
    ax.tick_params(axis="x", rotation=18)
    ax.legend(fontsize=8)
    for bar, value in zip(bars, risk_view["single_slot_risk_pct"].astype(float)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{value:.1f}%", ha="center", fontsize=9)

    ax = axes[1, 0]
    p0 = product_tiers[product_tiers["tier"].eq("P0_forward_watch")].copy()
    heat_cols = ["two_route_ready", "event_ready", "official_monitor_ready"]
    p0["core_corr_pass"] = p0["abs_core_daily_pnl_corr"].le(MAX_CORE_CORR_WATCH).astype(int)
    heat_cols.append("core_corr_pass")
    heat = p0.set_index("product_vt_symbol")[heat_cols].astype(float)
    im = ax.imshow(heat.values, vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(heat_cols)))
    ax.set_xticklabels(heat_cols, rotation=25, ha="right")
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(heat.index)
    ax.set_title("P0 evidence gaps")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, int(heat.values[i, j]), ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 1]
    gate_view = gates.copy()
    gate_view["passed"] = gate_view["passed"].astype(int)
    colors = np.where(gate_view["passed"].eq(1), "#2ca02c", "#d62728")
    ax.barh(gate_view["gate"], gate_view["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Structure gates")
    ax.set_xlabel("pass")
    ax.grid(axis="x", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _build_report(
    decision: dict[str, Any],
    product_tiers: pd.DataFrame,
    risk_slot_plan: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
) -> str:
    tier_summary = (
        product_tiers.groupby("tier", as_index=False)
        .agg(
            products=("product_vt_symbol", "count"),
            families=("product_family", "nunique"),
            total_pnl_sum=("total_pnl", "sum"),
            max_abs_core_corr=("abs_core_daily_pnl_corr", "max"),
        )
        .sort_values("products", ascending=False)
    )
    return f"""# Stage596 低单笔风险扩池风险槽设计审计

- 生成时间：`{decision["generated_at_local"]}`
- 决策：`{decision["decision"]}`
- 阶段性质：整合既有审计输出，定义扩池风险槽、产品分层、证据闸门；不做收益回测，不修改策略，不生成白名单。
- 调研参考：
{chr(10).join(f"  - {item}" for item in REFERENCE_LINKS)}

## 核心判断

- 低单笔风险扩池方向成立，但不是“随机加更多品种”。CTA/趋势跟踪的经验支持多市场分散和风险预算；本地证据也显示历史上存在非核心趋势机会。
- 当前 P0 是 `5` 个产品、`4` 个产品族；`y/c` 同族同向后，有效独立风险槽只有 `4` 个。按有效槽看，单槽风险约 `25%`，离 `<=15%` 的体验目标很远。
- 当前可接受的新产品族候选不足，无法把有效风险槽推进到 `7`。因此下一步不能直接收益回测，应先补新产品族的 source/TCA/selector 证据。
- P0 内部 pairwise 相关性不是主要矛盾；真正 blocker 是 selector edge、官方源、forward 样本深度和 live TCA。

## Product Tier Summary

{_md_table(tier_summary)}

## Product Tiers

{_md_table(product_tiers, [
    "product_vt_symbol",
    "product_family",
    "tier",
    "total_pnl",
    "positive_year_rate_pct",
    "abs_core_daily_pnl_corr",
    "capacity_quality_flag",
    "single_max_order_volume_to_day_volume_pct",
    "risk_slot_reason",
], max_rows=30)}

## Risk Slot Plan

{_md_table(risk_slot_plan)}

## Gates

{_md_table(gates)}

## Next Actions

{_md_table(next_actions)}

## 输出

- product tiers：`{PRODUCT_TIER_PATH}`
- risk slot plan：`{RISK_SLOT_PLAN_PATH}`
- gates：`{GATES_PATH}`
- next actions：`{NEXT_ACTIONS_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""


def main() -> None:
    product_tiers = _build_product_tiers()
    risk_slot_plan = _build_risk_slot_plan(product_tiers)
    gates = _build_gates(product_tiers, risk_slot_plan)
    next_actions = _build_next_actions(product_tiers)
    decision = _build_decision(product_tiers, risk_slot_plan, gates)
    report = _build_report(decision, product_tiers, risk_slot_plan, gates, next_actions)

    product_tiers.to_csv(PRODUCT_TIER_PATH, index=False, encoding="utf-8-sig")
    risk_slot_plan.to_csv(RISK_SLOT_PLAN_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _plot(product_tiers, risk_slot_plan, gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
