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


MODEL_TAG = "stage592_breadth_selector_structure_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage592_breadth_selector_structure_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE570_HOLDING = OUTPUT_DIR / "qmt_roll_stage570_breadth_holding_experience_audit_holding_summary_stage570_breadth_holding_experience_audit_v1.csv"
STAGE574_CANDIDATE_MAP = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_candidate_map_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE574_RISK_SHELL = OUTPUT_DIR / "qmt_roll_stage574_low_single_risk_breadth_selector_boundary_risk_shell_boundary_stage574_low_single_risk_breadth_selector_boundary_v1.csv"
STAGE588_EVIDENCE = OUTPUT_DIR / "qmt_roll_stage588_p0_selector_evidence_priority_audit_evidence_matrix_stage588_p0_selector_evidence_priority_audit_v1.csv"
STAGE590_THRESHOLDS = OUTPUT_DIR / "qmt_roll_stage590_breadth_selector_edge_threshold_audit_thresholds_stage590_breadth_selector_edge_threshold_audit_v1.csv"
STAGE590_RANDOM = OUTPUT_DIR / "qmt_roll_stage590_breadth_selector_edge_threshold_audit_random_distribution_stage590_breadth_selector_edge_threshold_audit_v1.csv"
STAGE561_GATES = OUTPUT_DIR / "qmt_roll_stage561_selector_predictive_audit_protocol_gates_stage561_selector_predictive_audit_protocol_v1.csv"
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / "qmt_roll_stage571_external_selector_source_priority_audit_source_priority_stage571_external_selector_source_priority_audit_v1.csv"
STAGE583_TCA_GATES = OUTPUT_DIR / "qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_gates_stage583_stage526_live_tca_evidence_gap_audit_v1.csv"
STAGE591_SUBMIT_GATES = OUTPUT_DIR / "qmt_roll_stage591_stage526_bridge_submit_adapter_dry_run_gates_stage591_stage526_bridge_submit_adapter_dry_run_v1.csv"

PRODUCT_BUDGET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_budget_{MODEL_TAG}.csv"
FAMILY_BUDGET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_budget_{MODEL_TAG}.csv"
STRUCTURE_GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_structure_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BASE_VARIANT = "stage526_r080_pc25_maxpos4"
UPPER_VARIANT = "dynamic_prevtop6_r050_pc15_maxpos3"
DEPLOYABLE_VARIANTS = [
    "breadth_all_noncore_r020_famcap20_corr5075_maxpos8",
    "breadth_prevpos_r020_famcap20_corr5075_maxpos8",
    "breadth_prevpos_r015_famcap15_corr5075_maxpos10",
]

MIN_PIT_PRODUCTS = 6
MIN_PIT_FAMILIES = 5
MAX_PRODUCT_RISK_HARD_PCT = 20.0
MAX_PRODUCT_RISK_PREFERRED_PCT = 15.0
MAX_FAMILY_RISK_PCT = 20.0
MAX_PAIRWISE_ABS_CORR = 0.50
MAX_CORE_ABS_CORR_WATCH = 0.10
MIN_ROUTE_READY_PRODUCTS = 5
MIN_EVENT_READY_PRODUCTS = 5
MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_ACTUAL_SLEEVE_PNL = 50_000.0
MIN_SELECTOR_CAPTURE_PCT = 92.58401999814832
MAX_TOP1_PRODUCT_SHARE_PCT = 35.0
MAX_TOP1_FAMILY_SHARE_PCT = 50.0
MIN_VALID_TCA_SAMPLES = 9


REFERENCE_LINKS = [
    "Moskowitz/Ooi/Pedersen Time Series Momentum: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2089463_code753937.pdf?abstractid=2089463&mirid=1",
    "pysystemtrade backtesting and instrument diversification: https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md",
    "Increasing Diversification of Commodities Trend-Following Strategies: https://papers.ssrn.com/sol3/Delivery.cfm/4871376.pdf?abstractid=4871376&mirid=1",
    "Concretum position sizing in trend-following: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
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


def _gate_value(gates: pd.DataFrame, gate: str, field: str = "current", default: str = "") -> str:
    if gates.empty or "gate" not in gates.columns or field not in gates.columns:
        return default
    rows = gates[gates["gate"].astype(str).eq(gate)]
    if rows.empty:
        return default
    return str(rows[field].iloc[0])


def _gate_passed(gates: pd.DataFrame, gate: str) -> bool:
    if gates.empty or "gate" not in gates.columns or "passed" not in gates.columns:
        return False
    rows = gates[gates["gate"].astype(str).eq(gate)]
    if rows.empty:
        return False
    value = rows["passed"].iloc[0]
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _build_product_budget() -> pd.DataFrame:
    candidate = _read_csv(STAGE574_CANDIDATE_MAP)
    evidence = _read_csv(STAGE588_EVIDENCE)

    p0 = candidate[candidate["independent_material_capacity_ok"].eq(1)].copy()
    keep_cols = [
        "product_vt_symbol",
        "product_family",
        "total_pnl",
        "positive_year_rate_pct",
        "abs_core_daily_pnl_corr",
        "capacity_quality_flag",
        "single_volume_data_coverage_rate_pct",
        "single_hard_volume_stress_event_rate_pct",
        "single_max_order_volume_to_day_volume_pct",
        "max_broker10_margin_to_sleeve_equity_pct",
        "watch_priority",
    ]
    p0 = p0[[column for column in keep_cols if column in p0.columns]].copy()
    p0 = p0.merge(evidence, on=["product_vt_symbol", "product_family"], how="left", suffixes=("", "_evidence"))

    product_count = max(len(p0), 1)
    p0["raw_equal_product_risk_pct"] = 100.0 / product_count
    p0["hard_product_risk_pass"] = p0["raw_equal_product_risk_pct"].le(MAX_PRODUCT_RISK_HARD_PCT).astype(int)
    p0["preferred_product_risk_pass"] = p0["raw_equal_product_risk_pct"].le(MAX_PRODUCT_RISK_PREFERRED_PCT).astype(int)
    p0["core_corr_watch_pass"] = _num(p0, "abs_core_daily_pnl_corr").le(MAX_CORE_ABS_CORR_WATCH).astype(int)
    p0["two_route_ready"] = _num(p0, "two_route_ready").astype(int)
    p0["event_ready"] = _num(p0, "event_ready").astype(int)
    p0["same_family_tiebreak_required"] = _num(p0, "same_family_tiebreak_required").astype(int)
    p0["structure_role"] = np.select(
        [
            p0["two_route_ready"].eq(1) & p0["event_ready"].eq(1) & p0["same_family_tiebreak_required"].eq(0) & p0["core_corr_watch_pass"].eq(1),
            p0["two_route_ready"].eq(1) & p0["event_ready"].eq(1) & p0["same_family_tiebreak_required"].eq(1),
            p0["two_route_ready"].eq(1) & p0["event_ready"].eq(0),
            p0["two_route_ready"].eq(0),
        ],
        [
            "ready_for_forward_selector_if_sample_depth_passes",
            "route_event_ready_but_family_tiebreak_needed",
            "route_ready_event_gap",
            "source_route_gap",
        ],
        default="observe",
    )
    sort_cols = ["two_route_ready", "event_ready", "total_pnl"]
    p0 = p0.sort_values(sort_cols, ascending=[False, False, False]).reset_index(drop=True)
    return p0


def _build_family_budget(product_budget: pd.DataFrame) -> pd.DataFrame:
    if product_budget.empty:
        return pd.DataFrame()
    product_count = len(product_budget)
    rows: list[dict[str, Any]] = []
    for family, group in product_budget.groupby("product_family", sort=False):
        raw_risk = len(group) / product_count * 100.0
        tiebreak_risk = 1 / product_count * 100.0
        rows.append(
            {
                "product_family": family,
                "products": ",".join(group["product_vt_symbol"].astype(str).tolist()),
                "product_count": int(len(group)),
                "raw_equal_family_risk_pct": raw_risk,
                "top1_tiebreak_family_risk_pct": tiebreak_risk,
                "raw_family_budget_pass": int(raw_risk <= MAX_FAMILY_RISK_PCT),
                "top1_tiebreak_budget_pass": int(tiebreak_risk <= MAX_FAMILY_RISK_PCT),
                "tiebreak_required": int(len(group) > 1),
                "action": "同族同向top1-only；无事前排序则禁同时开" if len(group) > 1 else "可按单产品预算观察",
            }
        )
    return pd.DataFrame(rows).sort_values(["raw_equal_family_risk_pct", "product_family"], ascending=[False, True])


def _safe_metric(frame: pd.DataFrame, variant: str, column: str, default: float = np.nan) -> float:
    rows = frame[frame["variant"].astype(str).eq(variant)]
    if rows.empty or column not in rows.columns:
        return default
    return float(pd.to_numeric(rows[column], errors="coerce").fillna(default).iloc[0])


def _parse_first_float(text: str, default: float = np.nan) -> float:
    import re

    match = re.search(r"-?\d+(?:\.\d+)?", str(text))
    if not match:
        return default
    return float(match.group(0))


def _build_structure_gates(product_budget: pd.DataFrame, family_budget: pd.DataFrame) -> pd.DataFrame:
    risk_shell = _read_csv(STAGE574_RISK_SHELL)
    holding = _read_csv(STAGE570_HOLDING)
    evidence = _read_csv(STAGE588_EVIDENCE)
    thresholds = _read_csv(STAGE590_THRESHOLDS)
    random_dist = _read_csv(STAGE590_RANDOM)
    stage561 = _read_csv(STAGE561_GATES)
    stage583 = _read_csv(STAGE583_TCA_GATES)
    stage591 = _read_csv(STAGE591_SUBMIT_GATES)

    p0_count = len(product_budget)
    p0_families = int(product_budget["product_family"].nunique()) if not product_budget.empty else 0
    route_ready_products = int(_num(product_budget, "two_route_ready").sum()) if not product_budget.empty else 0
    event_ready_products = int(_num(product_budget, "event_ready").sum()) if not product_budget.empty else 0
    max_pairwise_corr = float(_num(product_budget, "max_abs_pairwise_corr_in_p0").max()) if "max_abs_pairwise_corr_in_p0" in product_budget.columns else np.nan
    max_core_corr = float(_num(product_budget, "abs_core_daily_pnl_corr").max()) if not product_budget.empty else np.nan
    raw_family_budget_pass = int((family_budget["raw_family_budget_pass"].eq(1)).all()) if not family_budget.empty else 0
    tiebreak_family_budget_pass = int((family_budget["top1_tiebreak_budget_pass"].eq(1)).all()) if not family_budget.empty else 0

    actual_upper = thresholds[thresholds["metric"].eq("actual_stage256_upper_sleeve_pnl")]
    actual_all = thresholds[thresholds["metric"].eq("actual_all_noncore_sleeve_pnl")]
    p0_capture = thresholds[thresholds["metric"].eq("p0_fixed_watchlist_opportunity_capture_vs_hindsight_top6_pct")]
    random_p95 = random_dist[random_dist["mode"].eq("random_familycap_k6")]

    stage256_actual_pnl = float(pd.to_numeric(actual_upper["value"], errors="coerce").iloc[0]) if not actual_upper.empty else np.nan
    all_noncore_actual_pnl = float(pd.to_numeric(actual_all["value"], errors="coerce").iloc[0]) if not actual_all.empty else np.nan
    p0_capture_pct = float(pd.to_numeric(p0_capture["value"], errors="coerce").iloc[0]) if not p0_capture.empty else np.nan
    random_familycap_k6_p95 = float(pd.to_numeric(random_p95["total_pnl_p95"], errors="coerce").iloc[0]) if not random_p95.empty else np.nan

    forward_runs = _parse_first_float(_gate_value(stage561, "forward_runs_ready", "current", "0"))
    forward_dates = _parse_first_float(_gate_value(stage561, "forward_dates_ready", "current", "0"))

    deployable_no_degrade = risk_shell[risk_shell["variant"].isin(DEPLOYABLE_VARIANTS)].copy()
    deployable_no_degrade_count = int(_num(deployable_no_degrade, "deployable_no_degrade_pass").sum()) if not deployable_no_degrade.empty else 0
    stage256_no_degrade = int(_safe_metric(risk_shell, UPPER_VARIANT, "no_degrade_pass", 0.0))
    stage256_material = int(_safe_metric(risk_shell, UPPER_VARIANT, "materiality_pass", 0.0))
    all_noncore_material = int(_safe_metric(risk_shell, DEPLOYABLE_VARIANTS[0], "materiality_pass", 0.0))

    stage256_hold63_p10_delta = _safe_metric(risk_shell, UPPER_VARIANT, "hold63_p10_delta_vs_stage526", np.nan)
    stage256_hold126_p10_delta = _safe_metric(risk_shell, UPPER_VARIANT, "hold126_p10_delta_vs_stage526", np.nan)
    best_deployable_hold63 = float(deployable_no_degrade["hold63_p10_delta_vs_stage526"].max()) if "hold63_p10_delta_vs_stage526" in deployable_no_degrade.columns else np.nan
    best_deployable_hold126 = float(deployable_no_degrade["hold126_p10_delta_vs_stage526"].max()) if "hold126_p10_delta_vs_stage526" in deployable_no_degrade.columns else np.nan

    valid_live_tca_gate = stage583[stage583["gate"].eq("valid_live_tca_samples_complete")]
    valid_tca_samples = _parse_first_float(str(valid_live_tca_gate["actual"].iloc[0])) if not valid_live_tca_gate.empty else 0.0
    submit_payload_ready = _gate_passed(stage591, "order_request_payload_built")
    real_vt_orderid_absent = _gate_passed(stage591, "real_vt_orderid_absent")

    gates = [
        {
            "gate": "p0_pool_depth",
            "actual": f"{p0_count} products / {p0_families} families",
            "threshold": f">={MIN_PIT_PRODUCTS} products and >={MIN_PIT_FAMILIES} families",
            "passed": int(p0_count >= MIN_PIT_PRODUCTS and p0_families >= MIN_PIT_FAMILIES),
            "hard_gate": 1,
            "judgement": "池深度不足会让单品种贡献继续集中。",
        },
        {
            "gate": "single_product_risk_hard",
            "actual": f"{100.0 / max(p0_count, 1):.2f}% equal P0 product risk",
            "threshold": f"<={MAX_PRODUCT_RISK_HARD_PCT:.0f}% hard / <={MAX_PRODUCT_RISK_PREFERRED_PCT:.0f}% preferred",
            "passed": int((100.0 / max(p0_count, 1)) <= MAX_PRODUCT_RISK_HARD_PCT),
            "hard_gate": 1,
            "judgement": "当前5个P0刚好满足20%硬线，但未达到15%偏好线。",
        },
        {
            "gate": "family_budget_after_tiebreak",
            "actual": f"raw pass={raw_family_budget_pass}, top1 tiebreak pass={tiebreak_family_budget_pass}",
            "threshold": f"family risk <= {MAX_FAMILY_RISK_PCT:.0f}% after predeclared tie-break",
            "passed": int(tiebreak_family_budget_pass == 1),
            "hard_gate": 1,
            "judgement": "y/c 同属油脂油料，必须同族同向top1-only。",
        },
        {
            "gate": "pairwise_corr_budget",
            "actual": f"max P0 abs pairwise corr={max_pairwise_corr:.4f}",
            "threshold": f"<={MAX_PAIRWISE_ABS_CORR:.2f}",
            "passed": int(max_pairwise_corr <= MAX_PAIRWISE_ABS_CORR),
            "hard_gate": 1,
            "judgement": "P0内部相关性不是当前主要矛盾。",
        },
        {
            "gate": "core_corr_watch",
            "actual": f"max abs core corr={max_core_corr:.4f}",
            "threshold": f"<={MAX_CORE_ABS_CORR_WATCH:.2f} preferred; watch if above",
            "passed": int(max_core_corr <= MAX_CORE_ABS_CORR_WATCH),
            "hard_gate": 0,
            "judgement": "lu 历史贡献高，但与核心相关超过观察线。",
        },
        {
            "gate": "p0_route_ready",
            "actual": f"{route_ready_products}/{MIN_ROUTE_READY_PRODUCTS}",
            "threshold": f"{MIN_ROUTE_READY_PRODUCTS}/{MIN_ROUTE_READY_PRODUCTS}",
            "passed": int(route_ready_products >= MIN_ROUTE_READY_PRODUCTS),
            "hard_gate": 1,
            "judgement": "ao/lu 缺 basis 或替代路线。",
        },
        {
            "gate": "p0_event_ready",
            "actual": f"{event_ready_products}/{MIN_EVENT_READY_PRODUCTS}",
            "threshold": f"{MIN_EVENT_READY_PRODUCTS}/{MIN_EVENT_READY_PRODUCTS}",
            "passed": int(event_ready_products >= MIN_EVENT_READY_PRODUCTS),
            "hard_gate": 1,
            "judgement": "v/ao/lu 真实事件或舆情覆盖不足。",
        },
        {
            "gate": "forward_sample_depth",
            "actual": f"runs={forward_runs:.0f}, dates={forward_dates:.0f}",
            "threshold": f"runs>={MIN_FORWARD_RUNS}, dates>={MIN_FORWARD_DATES}",
            "passed": int(forward_runs >= MIN_FORWARD_RUNS and forward_dates >= MIN_FORWARD_DATES),
            "hard_gate": 1,
            "judgement": "当前只能 forward collection，不能做selector收益回测。",
        },
        {
            "gate": "selector_edge_threshold",
            "actual": f"P0 capture={p0_capture_pct:.2f}%, needed~{MIN_SELECTOR_CAPTURE_PCT:.2f}%",
            "threshold": f">={MIN_SELECTOR_CAPTURE_PCT:.2f}% of hindsight top6 opportunity proxy",
            "passed": int(p0_capture_pct >= MIN_SELECTOR_CAPTURE_PCT),
            "hard_gate": 1,
            "judgement": "历史P0机会有材料性，但距离可部署selector门槛很远。",
        },
        {
            "gate": "random_familycap_insufficient",
            "actual": f"familycap k6 p95 opportunity={random_familycap_k6_p95:.2f}",
            "threshold": "must remain below materiality proxy to prove selector edge is mandatory",
            "passed": int(random_familycap_k6_p95 < 396_870.66),
            "hard_gate": 0,
            "judgement": "随机低相关扩池不足以自然抓趋势。",
        },
        {
            "gate": "deployable_risk_shell_no_degrade",
            "actual": f"{deployable_no_degrade_count}/3 deployable shells",
            "threshold": "all proposed deployable shells must not degrade DD/Ulcer/3m/6m left tail",
            "passed": int(deployable_no_degrade_count == len(DEPLOYABLE_VARIANTS)),
            "hard_gate": 1,
            "judgement": "现有可部署宽池壳全部不能晋级。",
        },
        {
            "gate": "hindsight_upper_bound_exists",
            "actual": f"Stage256 sleeve={stage256_actual_pnl:.0f}, 63d delta={stage256_hold63_p10_delta:.4f}, 126d delta={stage256_hold126_p10_delta:.4f}",
            "threshold": f"upper actual sleeve >= {MIN_ACTUAL_SLEEVE_PNL:.0f} and holding deltas > 0",
            "passed": int(stage256_material == 1 and stage256_no_degrade == 1 and stage256_hold63_p10_delta > 0 and stage256_hold126_p10_delta > 0),
            "hard_gate": 0,
            "judgement": "历史上界说明方向值得做，但不能部署。",
        },
        {
            "gate": "naive_breadth_materiality",
            "actual": f"all noncore actual sleeve={all_noncore_actual_pnl:.0f}, material pass={all_noncore_material}",
            "threshold": f">={MIN_ACTUAL_SLEEVE_PNL:.0f}",
            "passed": int(all_noncore_material == 1),
            "hard_gate": 1,
            "judgement": "全非核心扩池收益太小，不能替代选品。",
        },
        {
            "gate": "holding_experience_no_degrade",
            "actual": f"best deployable 63d p10 delta={best_deployable_hold63:.4f}, 126d p10 delta={best_deployable_hold126:.4f}",
            "threshold": "best deployable 63d and 126d p10 deltas >= 0",
            "passed": int(best_deployable_hold63 >= 0 and best_deployable_hold126 >= 0),
            "hard_gate": 1,
            "judgement": "可部署宽池没有改善任意启动后的3/6个月左尾。",
        },
        {
            "gate": "contribution_concentration",
            "actual": f"Stage526 top1 product={_safe_metric(risk_shell, BASE_VARIANT, 'avg_top1_product_share_pct', np.nan):.2f}%, family={_safe_metric(risk_shell, BASE_VARIANT, 'avg_top1_family_share_pct', np.nan):.2f}%",
            "threshold": f"top1 product <= {MAX_TOP1_PRODUCT_SHARE_PCT:.0f}%, family <= {MAX_TOP1_FAMILY_SHARE_PCT:.0f}%",
            "passed": int(_safe_metric(risk_shell, BASE_VARIANT, "avg_top1_product_share_pct", np.nan) <= MAX_TOP1_PRODUCT_SHARE_PCT and _safe_metric(risk_shell, BASE_VARIANT, "avg_top1_family_share_pct", np.nan) <= MAX_TOP1_FAMILY_SHARE_PCT),
            "hard_gate": 0,
            "judgement": "年度贡献仍由少数产品/产品族主导，扩池结构必须改善这一点。",
        },
        {
            "gate": "live_tca_samples",
            "actual": f"{valid_tca_samples:.0f}/{MIN_VALID_TCA_SAMPLES} valid P0 samples",
            "threshold": f">={MIN_VALID_TCA_SAMPLES}",
            "passed": int(valid_tca_samples >= MIN_VALID_TCA_SAMPLES),
            "hard_gate": 1,
            "judgement": "真实成交偏差仍未关闭。",
        },
        {
            "gate": "submit_adapter_real_mapping",
            "actual": f"payload_ready={submit_payload_ready}, real_vt_orderid_absent={real_vt_orderid_absent}",
            "threshold": "payload ready and real vt_orderid mappings present before zero-bias claim",
            "passed": int(submit_payload_ready and not real_vt_orderid_absent),
            "hard_gate": 1,
            "judgement": "adapter dry-run ready，但真实 vt_orderid 仍为0。",
        },
    ]
    return pd.DataFrame(gates)


def _build_next_actions(product_budget: pd.DataFrame, family_budget: pd.DataFrame, structure_gates: pd.DataFrame) -> pd.DataFrame:
    source_priority = _read_csv(STAGE571_SOURCE_PRIORITY)
    rows: list[dict[str, Any]] = []

    for _, product in product_budget.iterrows():
        gaps = str(product.get("primary_gap", "")).split(",")
        for gap in gaps:
            gap = gap.strip()
            if not gap:
                continue
            if "basis" in gap:
                action = "补 basis 或可点时化替代路线"
            elif "sentiment" in gap or "event" in gap:
                action = "补真实事件/舆情账本，必须有 source_url/published_at/received_at/raw_hash"
            elif "same_family" in gap:
                action = "执行同族同向 top1-only tie-break，不允许 y/c 同向同时吃满"
            elif "core_corr" in gap:
                action = "标记核心相关观察线，future selector 不得让该产品单年主导"
            else:
                action = "补缺口证据"
            rows.append(
                {
                    "scope": "product",
                    "target": product["product_vt_symbol"],
                    "priority": int(100 - float(product.get("evidence_score_0_100", 0.0))),
                    "current_gap": gap,
                    "required_action": action,
                    "done_condition": "进入 Stage561 20/20 forward 样本后仍通过固定 IC/bucket/paper-sleeve 审计",
                }
            )

    for _, family in family_budget.iterrows():
        if int(family["tiebreak_required"]) == 1:
            rows.append(
                {
                    "scope": "family_budget",
                    "target": family["product_family"],
                    "priority": 90,
                    "current_gap": "same_family_risk_overlap",
                    "required_action": "预注册同族同向 top1-only，排序只允许来自点时化外生证据，不允许历史收益白名单",
                    "done_condition": "实盘前 selector 输出只能保留 y/c 之一，且日志可复验",
                }
            )

    hard_failed = structure_gates[(structure_gates["hard_gate"].eq(1)) & (structure_gates["passed"].eq(0))]
    for _, gate in hard_failed.iterrows():
        rows.append(
            {
                "scope": "structure_gate",
                "target": gate["gate"],
                "priority": 80,
                "current_gap": gate["actual"],
                "required_action": gate["judgement"],
                "done_condition": gate["threshold"],
            }
        )

    if rows:
        out = pd.DataFrame(rows)
        out = out.sort_values(["priority", "scope", "target"], ascending=[False, True, True]).reset_index(drop=True)
    else:
        out = pd.DataFrame(columns=["scope", "target", "priority", "current_gap", "required_action", "done_condition"])
    return out


def _plot(product_budget: pd.DataFrame, family_budget: pd.DataFrame, structure_gates: pd.DataFrame) -> None:
    risk_shell = _read_csv(STAGE574_RISK_SHELL)
    random_dist = _read_csv(STAGE590_RANDOM)
    stage561 = _read_csv(STAGE561_GATES)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("Stage592 Breadth Selector Structure Audit", fontsize=16, fontweight="bold")

    ax = axes[0, 0]
    colors = np.where(product_budget["event_ready"].eq(1), "#2ca02c", "#d62728")
    ax.scatter(
        _num(product_budget, "abs_core_daily_pnl_corr"),
        _num(product_budget, "total_pnl"),
        s=120,
        c=colors,
        alpha=0.85,
        edgecolor="black",
        linewidth=0.5,
    )
    for _, row in product_budget.iterrows():
        ax.annotate(str(row["product_vt_symbol"]), (row["abs_core_daily_pnl_corr"], row["total_pnl"]), xytext=(5, 5), textcoords="offset points", fontsize=9)
    ax.axvline(MAX_CORE_ABS_CORR_WATCH, color="#ff7f0e", linestyle="--", linewidth=1.5, label="core corr watch")
    ax.set_title("P0 opportunity vs core correlation")
    ax.set_xlabel("abs corr with Stage526 daily PnL")
    ax.set_ylabel("standalone opportunity")
    ax.legend(loc="upper left", fontsize=8)

    ax = axes[0, 1]
    variants = [UPPER_VARIANT] + DEPLOYABLE_VARIANTS
    labels = []
    delta63 = []
    delta126 = []
    for variant in variants:
        row = risk_shell[risk_shell["variant"].eq(variant)].iloc[0]
        labels.append(str(row["label_short"]))
        delta63.append(float(row["hold63_p10_delta_vs_stage526"]))
        delta126.append(float(row["hold126_p10_delta_vs_stage526"]))
    x = np.arange(len(labels))
    width = 0.36
    ax.bar(x - width / 2, delta63, width, label="63d p10 delta", color="#4c78a8")
    ax.bar(x + width / 2, delta126, width, label="126d p10 delta", color="#f58518")
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_title("Any-start 3m/6m left-tail delta")
    ax.set_ylabel("delta vs Stage526 (pct points)")
    ax.legend(fontsize=8)

    ax = axes[0, 2]
    metrics = ["route ready", "event ready", "forward runs", "forward dates", "valid TCA"]
    values = [
        float(_num(product_budget, "two_route_ready").sum()) / MIN_ROUTE_READY_PRODUCTS * 100.0,
        float(_num(product_budget, "event_ready").sum()) / MIN_EVENT_READY_PRODUCTS * 100.0,
        _parse_first_float(_gate_value(stage561, "forward_runs_ready", "current", "0")) / MIN_FORWARD_RUNS * 100.0,
        _parse_first_float(_gate_value(stage561, "forward_dates_ready", "current", "0")) / MIN_FORWARD_DATES * 100.0,
        0.0,
    ]
    colors = ["#2ca02c" if value >= 100 else "#d62728" for value in values]
    ax.bar(metrics, values, color=colors)
    ax.axhline(100, color="black", linestyle="--", linewidth=1)
    ax.set_ylim(0, 115)
    ax.set_title("Selector and execution readiness")
    ax.set_ylabel("% of gate")
    ax.tick_params(axis="x", rotation=20)
    for idx, value in enumerate(values):
        ax.text(idx, min(value + 3, 110), f"{value:.0f}%", ha="center", fontsize=9)

    ax = axes[1, 0]
    p95 = random_dist.set_index("mode")["total_pnl_p95"]
    p50 = random_dist.set_index("mode")["total_pnl_p50"]
    modes = list(p95.index)
    ax.bar(np.arange(len(modes)) - 0.17, p50.values, 0.34, label="p50", color="#9ecae9")
    ax.bar(np.arange(len(modes)) + 0.17, p95.values, 0.34, label="p95", color="#3182bd")
    ax.axhline(396_870.66, color="#d62728", linestyle="--", label="materiality proxy")
    ax.set_xticks(np.arange(len(modes)))
    ax.set_xticklabels(modes, rotation=25, ha="right")
    ax.set_title("Random breadth cannot replace selector")
    ax.set_ylabel("opportunity proxy")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    raw = family_budget["raw_equal_family_risk_pct"].values
    tie = family_budget["top1_tiebreak_family_risk_pct"].values
    labels = family_budget["product_family"].tolist()
    x = np.arange(len(labels))
    ax.bar(x - width / 2, raw, width, label="raw equal", color="#e45756")
    ax.bar(x + width / 2, tie, width, label="top1 tie-break", color="#54a24b")
    ax.axhline(MAX_FAMILY_RISK_PCT, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_title("Family risk budget")
    ax.set_ylabel("family risk pct")
    ax.legend(fontsize=8)

    ax = axes[1, 2]
    gates = structure_gates.copy()
    hard = gates[gates["hard_gate"].eq(1)].copy()
    soft = gates[gates["hard_gate"].eq(0)].copy()
    counts = [
        int(hard["passed"].sum()),
        int(len(hard) - hard["passed"].sum()),
        int(soft["passed"].sum()),
        int(len(soft) - soft["passed"].sum()),
    ]
    colors = ["#2ca02c", "#d62728", "#8bc34a", "#ff9800"]
    labels = ["hard pass", "hard fail", "soft pass", "soft fail"]
    ax.bar(labels, counts, color=colors)
    ax.set_title("Structure gates")
    ax.set_ylabel("count")
    for idx, value in enumerate(counts):
        ax.text(idx, value + 0.15, str(value), ha="center", fontsize=10)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(product_budget: pd.DataFrame, family_budget: pd.DataFrame, structure_gates: pd.DataFrame, next_actions: pd.DataFrame, decision: dict[str, Any]) -> None:
    hard = structure_gates[structure_gates["hard_gate"].eq(1)]
    hard_pass = int(hard["passed"].sum())
    hard_total = int(len(hard))
    soft = structure_gates[structure_gates["hard_gate"].eq(0)]
    soft_pass = int(soft["passed"].sum())
    soft_total = int(len(soft))
    failed_hard = hard[hard["passed"].eq(0)].copy()

    text = f"""# Stage592 Breadth Selector Structure Audit Report

- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- generated_at：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- decision：`{decision['decision']}`
- promotion_allowed：`{decision['promotion_allowed']}`
- paper_selector_allowed：`{decision['paper_selector_allowed']}`
- trading_whitelist_allowed：`{decision['trading_whitelist_allowed']}`
- hard_gates：`{hard_pass}/{hard_total}`
- soft_gates：`{soft_pass}/{soft_total}`

## External Research Judgment

- 多市场趋势跟随的长期证据支持分散化、波动率/风险预算和相关性治理。
- pysystemtrade/Rob Carver 类工程框架把 instrument weights、diversification multiplier、risk target 视为组合构造核心。
- 2024 年商品趋势扩散研究也支持扩大商品 universe 的潜在价值，但这不能替代 point-in-time selector。
- 本阶段判断：低单笔风险扩池方向成立，但当前不是可交易 alpha；真正缺口是 selector 证据和真实成交证据。

参考：
{chr(10).join(f"- {link}" for link in REFERENCE_LINKS)}

## Product Budget

{_md_table(product_budget, [
    'product_vt_symbol',
    'product_family',
    'total_pnl',
    'positive_year_rate_pct',
    'abs_core_daily_pnl_corr',
    'raw_equal_product_risk_pct',
    'two_route_ready',
    'event_ready',
    'evidence_score_0_100',
    'primary_gap',
    'structure_role',
])}

## Family Budget

{_md_table(family_budget)}

## Structure Gates

{_md_table(structure_gates)}

## Failed Hard Gates

{_md_table(failed_hard, ['gate', 'actual', 'threshold', 'judgement'])}

## Next Actions

{_md_table(next_actions, max_rows=40)}

## Interpretation

- 风险壳侧：P0 内部相关性通过，5个产品等权时单品种风险刚好为20%，但池深度未达6个产品/5个产品族，且 y/c 同族必须 top1-only。
- selector 侧：P0 固定篮子历史机会捕获只有约52.79%，低于约92.58%的可部署材料性门槛；随机 family-cap k6 的 p95 也远低于机会代理线，所以不能靠“随便扩池”抓趋势。
- 持有体验侧：只有 Stage256 hindsight upper 改善 63/126 日左尾；三个可部署宽池壳均未改善，说明现有 selector 不够。
- 执行侧：Stage591 dry-run adapter 能生成 payload，但真实 vt_orderid 和有效 live TCA 样本仍为0，不能宣称真实交易无偏差。

## Files

- product_budget：`{PRODUCT_BUDGET_PATH}`
- family_budget：`{FAMILY_BUDGET_PATH}`
- structure_gates：`{STRUCTURE_GATES_PATH}`
- next_actions：`{NEXT_ACTIONS_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_budget = _build_product_budget()
    family_budget = _build_family_budget(product_budget)
    structure_gates = _build_structure_gates(product_budget, family_budget)
    next_actions = _build_next_actions(product_budget, family_budget, structure_gates)

    hard = structure_gates[structure_gates["hard_gate"].eq(1)]
    soft = structure_gates[structure_gates["hard_gate"].eq(0)]
    hard_pass = int(hard["passed"].sum())
    hard_total = int(len(hard))
    soft_pass = int(soft["passed"].sum())
    soft_total = int(len(soft))

    promotion_allowed = hard_pass == hard_total and soft_pass >= max(1, soft_total - 1)
    paper_selector_allowed = bool(
        structure_gates.loc[structure_gates["gate"].eq("p0_route_ready"), "passed"].iloc[0]
        and structure_gates.loc[structure_gates["gate"].eq("p0_event_ready"), "passed"].iloc[0]
        and structure_gates.loc[structure_gates["gate"].eq("forward_sample_depth"), "passed"].iloc[0]
        and structure_gates.loc[structure_gates["gate"].eq("selector_edge_threshold"), "passed"].iloc[0]
    )
    trading_whitelist_allowed = bool(promotion_allowed and structure_gates.loc[structure_gates["gate"].eq("live_tca_samples"), "passed"].iloc[0])

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "breadth_selector_structure_promising_not_tradeable_selector_and_tca_blocked",
        "promotion_allowed": bool(promotion_allowed),
        "paper_selector_allowed": bool(paper_selector_allowed),
        "trading_whitelist_allowed": bool(trading_whitelist_allowed),
        "p0_products": int(len(product_budget)),
        "p0_families": int(product_budget["product_family"].nunique()) if not product_budget.empty else 0,
        "hard_gates_passed": hard_pass,
        "hard_gates_total": hard_total,
        "soft_gates_passed": soft_pass,
        "soft_gates_total": soft_total,
        "failed_hard_gates": hard.loc[hard["passed"].eq(0), "gate"].astype(str).tolist(),
        "main_judgement": "低单笔风险扩池是正确结构，但现有证据只支持 forward collection，不支持收益回测化 selector、P0交易白名单或A/B晋级。",
    }

    product_budget.to_csv(PRODUCT_BUDGET_PATH, index=False, encoding="utf-8-sig")
    family_budget.to_csv(FAMILY_BUDGET_PATH, index=False, encoding="utf-8-sig")
    structure_gates.to_csv(STRUCTURE_GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(product_budget, family_budget, structure_gates, next_actions, decision)
    _plot(product_budget, family_budget, structure_gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
