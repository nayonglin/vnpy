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


MODEL_TAG = "stage574_low_single_risk_breadth_selector_boundary_v1"
OUTPUT_PREFIX = "qmt_roll_stage574_low_single_risk_breadth_selector_boundary"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE541_ANNUAL = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv"
STAGE541_DAILY = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_daily_stage541_single_product_opportunity_map_v1.csv"
STAGE541_SUMMARY = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_summary_stage541_single_product_opportunity_map_v1.csv"
STAGE544_FAMILY = OUTPUT_DIR / "qmt_roll_stage544_family_constrained_selector_diagnostic_family_map_stage544_family_constrained_selector_diagnostic_v1.csv"
STAGE544_SUMMARY = OUTPUT_DIR / "qmt_roll_stage544_family_constrained_selector_diagnostic_summary_stage544_family_constrained_selector_diagnostic_v1.csv"
STAGE557_SUMMARY = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_summary_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE565_CAPACITY = OUTPUT_DIR / "qmt_roll_stage565_stage526_liquidity_capacity_product_audit_combined_product_capacity_stage565_stage526_liquidity_capacity_product_audit_v1.csv"
STAGE570_HOLDING = OUTPUT_DIR / "qmt_roll_stage570_breadth_holding_experience_audit_holding_summary_stage570_breadth_holding_experience_audit_v1.csv"
STAGE570_CONTRIB = OUTPUT_DIR / "qmt_roll_stage570_breadth_holding_experience_audit_contribution_summary_stage570_breadth_holding_experience_audit_v1.csv"
STAGE570_CROWDING = OUTPUT_DIR / "qmt_roll_stage570_breadth_holding_experience_audit_crowding_summary_stage570_breadth_holding_experience_audit_v1.csv"
STAGE558_GATES = OUTPUT_DIR / "qmt_roll_stage558_external_state_selector_readiness_audit_readiness_gates_stage558_external_state_selector_readiness_audit_v1.csv"
STAGE558_DECISION = OUTPUT_DIR / "qmt_roll_stage558_external_state_selector_readiness_audit_decision_stage558_external_state_selector_readiness_audit_v1.json"
STAGE561_DECISION = OUTPUT_DIR / "qmt_roll_stage561_selector_predictive_audit_protocol_decision_stage561_selector_predictive_audit_protocol_v1.json"

CANDIDATE_MAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_map_{MODEL_TAG}.csv"
ANNUAL_OPPORTUNITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_opportunity_{MODEL_TAG}.csv"
PAIRWISE_CORR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_corr_{MODEL_TAG}.csv"
RISK_SHELL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_shell_boundary_{MODEL_TAG}.csv"
SELECTOR_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selector_readiness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BASE_VARIANT = "stage526_r080_pc25_maxpos4"
UPPER_VARIANT = "dynamic_prevtop6_r050_pc15_maxpos3"
DEPLOYABLE_WIDTHS = (
    "breadth_all_noncore_r020_famcap20_corr5075_maxpos8",
    "breadth_prevpos_r020_famcap20_corr5075_maxpos8",
    "breadth_prevpos_r015_famcap15_corr5075_maxpos10",
)
VARIANT_LABELS = {
    BASE_VARIANT: "Stage526",
    UPPER_VARIANT: "Stage256 upper",
    "breadth_all_noncore_r020_famcap20_corr5075_maxpos8": "All noncore r020",
    "breadth_prevpos_r020_famcap20_corr5075_maxpos8": "Prev+ r020",
    "breadth_prevpos_r015_famcap15_corr5075_maxpos10": "Prev+ r015",
}

REFERENCE_LINKS = [
    "AQR Trend Following: https://www.aqr.com/insights/trend-following",
    "AQR Century of Trend Following evidence: https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing-executive-summ",
    "Increasing Diversification of Commodities Trend-Following Strategies: https://papers.ssrn.com/sol3/Delivery.cfm/4871376.pdf?abstractid=4871376&mirid=1",
    "GitHub PyTrendFollow engineering reference: https://github.com/chrism2671/PyTrendFollow",
    "GitHub MLM trend-following reference: https://github.com/amstrdm/mlm-trend-following",
]


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
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


def _build_candidate_map() -> pd.DataFrame:
    summary = _read_csv(STAGE541_SUMMARY)
    annual = _read_csv(STAGE541_ANNUAL)
    family = _read_csv(STAGE544_FAMILY)
    capacity = _read_csv(STAGE565_CAPACITY)

    frame = summary[summary["is_core_product"].eq(0)].copy()
    frame["abs_core_daily_pnl_corr"] = _num(frame, "core_daily_pnl_corr").abs()
    frame["candidate_materiality_pass"] = _num(frame, "candidate_materiality_pass").astype(int)
    frame = frame.merge(family[["product_vt_symbol", "product_family", "family_note"]], on="product_vt_symbol", how="left")

    cap_cols = [
        "product_vt_symbol",
        "capacity_quality_flag",
        "material_and_capacity_ok",
        "single_volume_data_coverage_rate_pct",
        "single_hard_volume_stress_event_rate_pct",
        "single_max_order_volume_to_day_volume_pct",
        "breadth_all_noncore_sleeve_pnl",
    ]
    cap_cols = [col for col in cap_cols if col in capacity.columns]
    frame = frame.merge(capacity[cap_cols], on="product_vt_symbol", how="left")

    annual = annual[annual["is_core_product"].eq(0)].copy()
    annual["net_pnl"] = _num(annual, "net_pnl")
    annual["trade_count"] = _num(annual, "trade_count")
    annual_stats = (
        annual.groupby("product_vt_symbol", as_index=False)
        .agg(
            annual_years=("year", "nunique"),
            positive_years=("net_pnl", lambda s: int((s > 0).sum())),
            active_years=("trade_count", lambda s: int((s > 0).sum())),
            worst_year_pnl=("net_pnl", "min"),
            best_year_pnl=("net_pnl", "max"),
            median_year_pnl=("net_pnl", "median"),
        )
        .copy()
    )
    annual_stats["positive_year_rate_pct"] = np.where(
        annual_stats["annual_years"] > 0,
        annual_stats["positive_years"] / annual_stats["annual_years"] * 100.0,
        0.0,
    )
    frame = frame.merge(annual_stats, on="product_vt_symbol", how="left")

    for column in [
        "total_pnl",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "recent_median_volume",
        "max_broker10_margin_to_sleeve_equity_pct",
        "single_volume_data_coverage_rate_pct",
        "single_hard_volume_stress_event_rate_pct",
        "single_max_order_volume_to_day_volume_pct",
        "breadth_all_noncore_sleeve_pnl",
    ]:
        frame[column] = _num(frame, column)
    frame["product_family"] = frame["product_family"].fillna("unknown")
    frame["family_note"] = frame["family_note"].fillna("")
    frame["capacity_quality_flag"] = frame["capacity_quality_flag"].fillna("unknown")
    frame["material_and_capacity_ok"] = _num(frame, "material_and_capacity_ok").astype(int)
    frame["independent_material_capacity_ok"] = (
        (frame["candidate_materiality_pass"].eq(1))
        & (frame["material_and_capacity_ok"].eq(1))
        & (frame["abs_core_daily_pnl_corr"].le(0.20))
    ).astype(int)
    frame["watch_priority"] = np.select(
        [
            frame["independent_material_capacity_ok"].eq(1),
            frame["candidate_materiality_pass"].eq(1) & frame["capacity_quality_flag"].isin(["green", "yellow"]),
            frame["total_pnl"].gt(0) & frame["abs_core_daily_pnl_corr"].le(0.20),
        ],
        ["P0_independent_material", "P1_material_capacity_watch", "P2_lowcorr_profitable_watch"],
        default="P3_reject_or_observe",
    )
    frame.sort_values(
        ["independent_material_capacity_ok", "candidate_materiality_pass", "total_pnl"],
        ascending=[False, False, False],
        inplace=True,
    )
    return frame


def _build_pairwise_corr(candidate_map: pd.DataFrame) -> pd.DataFrame:
    products = candidate_map.loc[candidate_map["independent_material_capacity_ok"].eq(1), "product_vt_symbol"].astype(str).tolist()
    if len(products) < 2:
        return pd.DataFrame()
    daily = _read_csv(STAGE541_DAILY, usecols=["date", "product_vt_symbol", "net_pnl"])
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily = daily[daily["date"].ge(pd.Timestamp("2021-01-01")) & daily["product_vt_symbol"].isin(products)].copy()
    daily["net_pnl"] = _num(daily, "net_pnl")
    pivot = daily.pivot_table(index="date", columns="product_vt_symbol", values="net_pnl", aggfunc="sum").fillna(0.0)
    corr = pivot.corr()
    rows: list[dict[str, Any]] = []
    for idx, left in enumerate(corr.columns):
        for right in corr.columns[idx + 1 :]:
            rows.append(
                {
                    "left_product": left,
                    "right_product": right,
                    "daily_pnl_corr": float(corr.loc[left, right]),
                    "abs_daily_pnl_corr": float(abs(corr.loc[left, right])),
                }
            )
    return pd.DataFrame(rows).sort_values("abs_daily_pnl_corr", ascending=False)


def _build_annual_opportunity(candidate_map: pd.DataFrame) -> pd.DataFrame:
    annual = _read_csv(STAGE541_ANNUAL)
    family = candidate_map[["product_vt_symbol", "product_family"]].drop_duplicates("product_vt_symbol")
    frame = annual[annual["is_core_product"].eq(0)].copy()
    frame["net_pnl"] = _num(frame, "net_pnl")
    frame["trade_count"] = _num(frame, "trade_count")
    frame = frame.merge(family, on="product_vt_symbol", how="left")
    rows: list[dict[str, Any]] = []
    for year, group in frame.groupby("year"):
        group = group.sort_values("net_pnl", ascending=False).copy()
        positive = group[group["net_pnl"] > 0.0]
        top6 = group.head(6)
        top6_families = top6["product_family"].dropna().astype(str)
        rows.append(
            {
                "year": int(year),
                "noncore_count": int(group["product_vt_symbol"].nunique()),
                "active_count": int(group.loc[group["trade_count"] > 0, "product_vt_symbol"].nunique()),
                "positive_count": int(positive["product_vt_symbol"].nunique()),
                "positive_pnl_sum": float(positive["net_pnl"].sum()),
                "top1_pnl": float(group.head(1)["net_pnl"].sum()),
                "top3_pnl": float(group.head(3)["net_pnl"].sum()),
                "top6_pnl": float(top6["net_pnl"].sum()),
                "top6_family_count": int(top6_families.nunique()),
                "top6_family_max_count": int(top6_families.value_counts().max()) if len(top6_families) else 0,
                "top6_products": ",".join(top6["product_vt_symbol"].astype(str).tolist()),
                "top6_families": ",".join(top6_families.tolist()),
                "top6_positive": int(top6["net_pnl"].sum() > 0.0 and len(positive) >= 3),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def _build_risk_shell_boundary() -> pd.DataFrame:
    summary = _read_csv(STAGE557_SUMMARY)
    holding = _read_csv(STAGE570_HOLDING)
    contrib = _read_csv(STAGE570_CONTRIB)
    crowding = _read_csv(STAGE570_CROWDING)

    frame = summary[summary["cost_multiplier"].eq(1.0)].copy()
    frame = frame[frame["variant"].isin([BASE_VARIANT, UPPER_VARIANT, *DEPLOYABLE_WIDTHS])].copy()
    frame["label_short"] = frame["variant"].map(VARIANT_LABELS).fillna(frame["label"])
    frame["deployable_status"] = np.where(frame["variant"].eq(UPPER_VARIANT), "hindsight_upper_bound", "deployable_or_control")
    frame.loc[frame["variant"].eq(BASE_VARIANT), "deployable_status"] = "control"

    for horizon in (63, 126):
        h = holding[holding["horizon_days"].eq(horizon)].copy()
        h = h[
            [
                "variant",
                "p10_return_pct",
                "p05_return_pct",
                "min_return_pct",
                "negative_rate_pct",
                "mae_p05_pct",
                "mae_min_pct",
                "p10_return_pct_delta_vs_stage526",
                "negative_rate_pct_delta_vs_stage526",
            ]
        ].rename(
            columns={
                "p10_return_pct": f"hold{horizon}_p10_return_pct",
                "p05_return_pct": f"hold{horizon}_p05_return_pct",
                "min_return_pct": f"hold{horizon}_min_return_pct",
                "negative_rate_pct": f"hold{horizon}_negative_rate_pct",
                "mae_p05_pct": f"hold{horizon}_mae_p05_pct",
                "mae_min_pct": f"hold{horizon}_mae_min_pct",
                "p10_return_pct_delta_vs_stage526": f"hold{horizon}_p10_delta_vs_stage526",
                "negative_rate_pct_delta_vs_stage526": f"hold{horizon}_negative_rate_delta_vs_stage526",
            }
        )
        frame = frame.merge(h, on="variant", how="left")

    contrib_cols = [
        "variant",
        "avg_top1_product_share_pct",
        "avg_top1_family_share_pct",
        "years_top1_product_over35",
        "years_top1_family_over50",
        "avg_positive_product_count",
        "avg_positive_family_count",
    ]
    frame = frame.merge(contrib[[col for col in contrib_cols if col in contrib.columns]], on="variant", how="left")
    crowd_cols = [
        "variant",
        "candidate_corr_gt50_count",
        "candidate_corr_gt75_count",
        "opened_corr_gt50_count",
        "opened_corr_gt75_count",
        "avg_abs_core_corr",
        "max_abs_core_corr",
        "avg_family_max_count",
    ]
    frame = frame.merge(crowding[[col for col in crowd_cols if col in crowding.columns]], on="variant", how="left")

    for column in frame.columns:
        if column not in {"variant", "label", "label_short", "note", "deployable_status"}:
            if frame[column].dtype == object:
                frame[column] = pd.to_numeric(frame[column], errors="ignore")

    base = frame[frame["variant"].eq(BASE_VARIANT)].iloc[0]
    frame["max_dd_delta_vs_stage526"] = _num(frame, "max_dd_pct") - float(base["max_dd_pct"])
    frame["ulcer_delta_vs_stage526"] = _num(frame, "ulcer_pct") - float(base["ulcer_pct"])
    frame["return_delta_vs_stage526_pct"] = _num(frame, "total_return_pct") - float(base["total_return_pct"])
    frame["deployable_no_degrade_pass"] = (
        frame["variant"].isin(DEPLOYABLE_WIDTHS)
        & frame["max_dd_delta_vs_stage526"].ge(0.0)
        & frame["ulcer_delta_vs_stage526"].le(0.0)
        & _num(frame, "hold63_p10_delta_vs_stage526").ge(0.0)
        & _num(frame, "hold126_p10_delta_vs_stage526").ge(0.0)
    ).astype(int)
    return frame


def _build_selector_readiness() -> pd.DataFrame:
    selector = _read_csv(STAGE544_SUMMARY)
    quarterly = selector[selector["sample_type"].eq("quarterly_purged")].copy()
    best = quarterly.sort_values(
        ["diagnostic_pass", "avg_edge_vs_all_future60", "positive_month_rate_future60_pct"],
        ascending=[False, False, False],
    ).head(1)
    stage558 = _read_json(STAGE558_DECISION)
    stage561 = _read_json(STAGE561_DECISION)
    progress = stage561.get("current_progress", {})
    req = stage561.get("hard_requirements_before_predictive_audit", {})
    gates = _read_csv(STAGE558_GATES)

    rows = [
        {
            "item": "best_quarterly_selector_pass",
            "value": int(best["diagnostic_pass"].iloc[0]) if not best.empty else 0,
            "required": 1,
            "passed": int(not best.empty and int(best["diagnostic_pass"].iloc[0]) == 1),
            "detail": best["mode_label"].iloc[0] if not best.empty else "no selector",
        },
        {
            "item": "best_quarterly_future60_edge",
            "value": float(best["avg_edge_vs_all_future60"].iloc[0]) if not best.empty else 0.0,
            "required": 500.0,
            "passed": int(not best.empty and float(best["avg_edge_vs_all_future60"].iloc[0]) >= 500.0),
            "detail": "Stage544 fixed hard edge threshold",
        },
        {
            "item": "qualified_forward_runs",
            "value": int(progress.get("forward_runs", progress.get("qualified_forward_runs", 0))),
            "required": int(req.get("min_forward_runs", 20)),
            "passed": int(int(progress.get("forward_runs", progress.get("qualified_forward_runs", 0))) >= int(req.get("min_forward_runs", 20))),
            "detail": stage561.get("decision", ""),
        },
        {
            "item": "qualified_forward_dates",
            "value": int(progress.get("forward_dates", progress.get("qualified_forward_dates", 0))),
            "required": int(req.get("min_forward_dates", 20)),
            "passed": int(int(progress.get("forward_dates", progress.get("qualified_forward_dates", 0))) >= int(req.get("min_forward_dates", 20))),
            "detail": f"next eligible {progress.get('next_eligible_collection_date', '')}",
        },
        {
            "item": "real_sentiment_ledger",
            "value": int(progress.get("real_sentiment_ledgers", progress.get("real_sentiment_news_ledger_count", 0))),
            "required": int(req.get("min_real_sentiment_ledgers", 1)),
            "passed": int(
                int(progress.get("real_sentiment_ledgers", progress.get("real_sentiment_news_ledger_count", 0)))
                >= int(req.get("min_real_sentiment_ledgers", 1))
            ),
            "detail": "real point-in-time event ledger count",
        },
        {
            "item": "history_selector_ready_products",
            "value": int(stage558.get("history_ready_products", 0)),
            "required": 0,
            "passed": int(int(stage558.get("history_ready_products", 0)) == 0),
            "detail": "must stay zero; no history-backfilled selector allowed",
        },
    ]
    if "passed" in gates.columns:
        rows.append(
            {
                "item": "stage558_readiness_gates",
                "value": int(pd.to_numeric(gates["passed"], errors="coerce").fillna(0).sum()),
                "required": int(len(gates)),
                "passed": int(pd.to_numeric(gates["passed"], errors="coerce").fillna(0).sum() == len(gates)),
                "detail": stage558.get("decision", ""),
            }
        )
    return pd.DataFrame(rows)


def _build_gates(
    candidate_map: pd.DataFrame,
    annual_opportunity: pd.DataFrame,
    pairwise_corr: pd.DataFrame,
    risk_shell: pd.DataFrame,
    selector_readiness: pd.DataFrame,
) -> pd.DataFrame:
    material = candidate_map[candidate_map["independent_material_capacity_ok"].eq(1)].copy()
    deployable = risk_shell[risk_shell["variant"].isin(DEPLOYABLE_WIDTHS)].copy()
    all_noncore = risk_shell[risk_shell["variant"].eq(DEPLOYABLE_WIDTHS[0])].iloc[0]
    selector_pass_count = int(selector_readiness["passed"].sum())
    selector_total = int(len(selector_readiness))
    avg_pair_abs_corr = float(pairwise_corr["abs_daily_pnl_corr"].mean()) if not pairwise_corr.empty else np.nan
    max_pair_abs_corr = float(pairwise_corr["abs_daily_pnl_corr"].max()) if not pairwise_corr.empty else np.nan
    rows = [
        {
            "gate": "annual_opportunity_exists",
            "actual": f"{int(annual_opportunity['top6_positive'].sum())}/{len(annual_opportunity)} years",
            "threshold": "all years top6 positive",
            "passed": int(annual_opportunity["top6_positive"].sum() == len(annual_opportunity)),
            "judgement": "非核心年度趋势机会真实存在；这是继续研究的必要条件。",
        },
        {
            "gate": "independent_material_capacity_pool_exists",
            "actual": f"{len(material)} products; avg_abs_core_corr={material['abs_core_daily_pnl_corr'].mean():.4f}",
            "threshold": ">=6 material capacity-ok products and avg abs core corr <=0.20",
            "passed": int(len(material) >= 6 and material["abs_core_daily_pnl_corr"].mean() <= 0.20),
            "judgement": "可研究的独立候选池存在，不应被流动性或核心相关性直接否决。",
        },
        {
            "gate": "candidate_pairwise_corr_not_crowded",
            "actual": f"avg_pair_abs_corr={avg_pair_abs_corr:.4f}, max_pair_abs_corr={max_pair_abs_corr:.4f}",
            "threshold": "avg <=0.20 and max <=0.50",
            "passed": int(not pairwise_corr.empty and avg_pair_abs_corr <= 0.20 and max_pair_abs_corr <= 0.50),
            "judgement": "低相关候选之间不能只是同一产业链的重复风险。",
        },
        {
            "gate": "deployable_width_no_degrade",
            "actual": f"{int(deployable['deployable_no_degrade_pass'].sum())}/{len(deployable)} deployable width shells",
            "threshold": "at least one deployable width shell improves DD/Ulcer/63d/126d p10",
            "passed": int(deployable["deployable_no_degrade_pass"].sum() >= 1),
            "judgement": "现有可部署宽池壳没有改善核心体验，不能晋级。",
        },
        {
            "gate": "plain_width_material_capture",
            "actual": f"satellite_pnl={float(all_noncore['satellite_cumulative_pnl']):.0f}, dd_delta={float(all_noncore['max_dd_delta_vs_stage526']):.4f}, ulcer_delta={float(all_noncore['ulcer_delta_vs_stage526']):.4f}",
            "threshold": "satellite pnl >=50000 and DD/Ulcer not worse than Stage526",
            "passed": int(
                float(all_noncore["satellite_cumulative_pnl"]) >= 50000.0
                and float(all_noncore["max_dd_delta_vs_stage526"]) >= 0.0
                and float(all_noncore["ulcer_delta_vs_stage526"]) <= 0.0
            ),
            "judgement": "盲目低单笔宽池没有抓住足够趋势收益。",
        },
        {
            "gate": "selector_readiness_for_trading_probe",
            "actual": f"{selector_pass_count}/{selector_total} readiness items",
            "threshold": "all readiness items pass before any trading probe",
            "passed": int(selector_pass_count == selector_total),
            "judgement": "点时 selector 样本深度尚未达到，禁止选品收益回测晋级。",
        },
    ]
    return pd.DataFrame(rows)


def _decision(
    candidate_map: pd.DataFrame,
    pairwise_corr: pd.DataFrame,
    risk_shell: pd.DataFrame,
    selector_readiness: pd.DataFrame,
    gates: pd.DataFrame,
) -> dict[str, Any]:
    material = candidate_map[candidate_map["independent_material_capacity_ok"].eq(1)].copy()
    deployable = risk_shell[risk_shell["variant"].isin(DEPLOYABLE_WIDTHS)].copy()
    stage256 = risk_shell[risk_shell["variant"].eq(UPPER_VARIANT)].iloc[0]
    stage526 = risk_shell[risk_shell["variant"].eq(BASE_VARIANT)].iloc[0]
    forward_runs = selector_readiness.loc[selector_readiness["item"].eq("qualified_forward_runs"), "value"].iloc[0]
    forward_dates = selector_readiness.loc[selector_readiness["item"].eq("qualified_forward_dates"), "value"].iloc[0]
    real_sentiment = selector_readiness.loc[selector_readiness["item"].eq("real_sentiment_ledger"), "value"].iloc[0]
    pair_stats = {
        "avg_abs_pairwise_corr": float(pairwise_corr["abs_daily_pnl_corr"].mean()) if not pairwise_corr.empty else None,
        "max_abs_pairwise_corr": float(pairwise_corr["abs_daily_pnl_corr"].max()) if not pairwise_corr.empty else None,
    }
    passed = int(gates["passed"].sum())
    decision = (
        "breadth_selector_trading_probe_allowed"
        if passed == len(gates)
        else "breadth_thesis_valid_selector_boundary_not_ready"
    )
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "summary": {
            "gate_pass_count": passed,
            "gate_count": int(len(gates)),
            "independent_material_capacity_ok_count": int(len(material)),
            "independent_material_capacity_ok_products": material["product_vt_symbol"].astype(str).tolist(),
            "independent_material_avg_abs_core_corr": float(material["abs_core_daily_pnl_corr"].mean()) if not material.empty else None,
            "pairwise_corr": pair_stats,
            "deployable_width_no_degrade_count": int(deployable["deployable_no_degrade_pass"].sum()),
            "stage526_total_return_pct": float(stage526["total_return_pct"]),
            "stage526_max_dd_pct": float(stage526["max_dd_pct"]),
            "stage526_ulcer_pct": float(stage526["ulcer_pct"]),
            "stage256_upper_holding_delta_63d_p10": float(stage256["hold63_p10_delta_vs_stage526"]),
            "stage256_upper_holding_delta_126d_p10": float(stage256["hold126_p10_delta_vs_stage526"]),
            "forward_runs": int(forward_runs),
            "forward_dates": int(forward_dates),
            "real_sentiment_ledgers": int(real_sentiment),
        },
        "judgement": (
            "The low-single-risk breadth idea remains valid because independent, capacity-ok, low-core-correlation "
            "products exist and annual hindsight opportunity is persistent. It is not promotable because deployable "
            "width shells do not improve DD/Ulcer/63d/126d holding experience, while the point-in-time selector still "
            "lacks 20/20 forward samples."
        ),
        "overfit_reflection": (
            "Not overfit: this stage does not use future winners to create a trading whitelist and does not sweep "
            "risk/correlation thresholds. It audits fixed prior outputs and freezes promotion gates."
        ),
        "continue_value_reflection": (
            "Worth continuing only through forward selector data and a fixed paper sleeve after sample maturity. "
            "Not worth continuing as parameter sweeps over width risk/cap/corr/maxpos."
        ),
        "next_step": (
            "Keep Stage526 as core. Continue point-in-time basis/inventory/sentiment collection to 20 qualified dates; "
            "then run the frozen IC/bucket/paper sleeve test before any dynamic breadth backtest."
        ),
        "references": REFERENCE_LINKS,
        "outputs": {
            "candidate_map": str(CANDIDATE_MAP_PATH),
            "annual_opportunity": str(ANNUAL_OPPORTUNITY_PATH),
            "pairwise_corr": str(PAIRWISE_CORR_PATH),
            "risk_shell": str(RISK_SHELL_PATH),
            "selector_readiness": str(SELECTOR_READINESS_PATH),
            "gates": str(GATES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }


def _plot(
    candidate_map: pd.DataFrame,
    annual_opportunity: pd.DataFrame,
    pairwise_corr: pd.DataFrame,
    risk_shell: pd.DataFrame,
    selector_readiness: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    ax_scatter, ax_annual, ax_shell, ax_holding, ax_selector, ax_gates = axes.flatten()

    plot_candidates = candidate_map[candidate_map["total_pnl"].ne(0)].copy()
    colors = {
        "energy_oil": "#f97316",
        "petrochem": "#8b5cf6",
        "grains_oilseeds": "#16a34a",
        "base_metals": "#2563eb",
        "black_ferrous": "#111827",
        "soft_agri": "#ec4899",
        "rubber": "#0f766e",
        "other": "#64748b",
    }
    for family, group in plot_candidates.groupby("product_family"):
        ax_scatter.scatter(
            group["abs_core_daily_pnl_corr"],
            group["total_pnl"],
            s=np.where(group["independent_material_capacity_ok"].eq(1), 80, 30),
            alpha=0.72,
            label=str(family),
            color=colors.get(str(family), "#64748b"),
            edgecolors="#ffffff",
            linewidths=0.4,
        )
    material = candidate_map[candidate_map["independent_material_capacity_ok"].eq(1)].head(10)
    for _, row in material.iterrows():
        ax_scatter.annotate(str(row["product_vt_symbol"]), (row["abs_core_daily_pnl_corr"], row["total_pnl"]), fontsize=7)
    ax_scatter.axvline(0.20, color="#dc2626", linestyle=":", linewidth=1)
    ax_scatter.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_scatter.set_title("Noncore single-product opportunity vs core correlation")
    ax_scatter.set_xlabel("abs corr to Stage526 daily PnL")
    ax_scatter.set_ylabel("single-product total PnL")
    ax_scatter.grid(alpha=0.25)
    ax_scatter.legend(fontsize=6, ncol=2, loc="best")

    ax_annual.bar(annual_opportunity["year"].astype(str), annual_opportunity["top6_pnl"], color="#2563eb", label="top6 PnL")
    ax_annual.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_annual.set_title("Annual noncore hindsight opportunity")
    ax_annual.set_ylabel("top6 PnL")
    ax_annual.grid(axis="y", alpha=0.25)
    ax_annual_count = ax_annual.twinx()
    ax_annual_count.plot(
        annual_opportunity["year"].astype(str),
        annual_opportunity["positive_count"],
        color="#f97316",
        marker="o",
        label="positive product count",
    )
    ax_annual_count.set_ylabel("positive product count")
    handles1, labels1 = ax_annual.get_legend_handles_labels()
    handles2, labels2 = ax_annual_count.get_legend_handles_labels()
    ax_annual.legend(handles1 + handles2, labels1 + labels2, fontsize=7, loc="upper right")

    shell = risk_shell[risk_shell["variant"].isin([BASE_VARIANT, UPPER_VARIANT, *DEPLOYABLE_WIDTHS])].copy()
    x = np.arange(len(shell))
    ax_shell.bar(x - 0.18, shell["max_dd_delta_vs_stage526"], width=0.36, label="DD delta vs Stage526", color="#0ea5e9")
    ax_shell.bar(x + 0.18, -shell["ulcer_delta_vs_stage526"], width=0.36, label="-Ulcer delta vs Stage526", color="#10b981")
    ax_shell.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_shell.set_xticks(x)
    ax_shell.set_xticklabels(shell["label_short"], rotation=25, ha="right", fontsize=8)
    ax_shell.set_title("Path quality delta: positive is better")
    ax_shell.grid(axis="y", alpha=0.25)
    ax_shell.legend(fontsize=7)

    ax_holding.bar(x - 0.18, shell["hold63_p10_delta_vs_stage526"], width=0.36, label="63d p10 delta", color="#7c3aed")
    ax_holding.bar(x + 0.18, shell["hold126_p10_delta_vs_stage526"], width=0.36, label="126d p10 delta", color="#f59e0b")
    ax_holding.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_holding.set_xticks(x)
    ax_holding.set_xticklabels(shell["label_short"], rotation=25, ha="right", fontsize=8)
    ax_holding.set_title("3/6 month holding-experience delta")
    ax_holding.grid(axis="y", alpha=0.25)
    ax_holding.legend(fontsize=7)

    selector = selector_readiness.copy()
    selector["ratio_pct"] = np.where(
        pd.to_numeric(selector["required"], errors="coerce").astype(float) != 0,
        pd.to_numeric(selector["value"], errors="coerce").astype(float)
        / pd.to_numeric(selector["required"], errors="coerce").astype(float)
        * 100.0,
        0.0,
    )
    selector_plot = selector[selector["item"].isin(["qualified_forward_runs", "qualified_forward_dates", "real_sentiment_ledger", "stage558_readiness_gates"])].copy()
    colors_selector = np.where(selector_plot["passed"].eq(1), "#10b981", "#dc2626")
    ax_selector.barh(selector_plot["item"], selector_plot["ratio_pct"], color=colors_selector)
    ax_selector.axvline(100, color="#111827", linestyle="--", linewidth=1)
    ax_selector.set_title("Point-in-time selector readiness")
    ax_selector.set_xlabel("% of requirement")
    ax_selector.grid(axis="x", alpha=0.25)

    gate_colors = np.where(gates["passed"].eq(1), "#10b981", "#dc2626")
    ax_gates.barh(gates["gate"], np.ones(len(gates)), color=gate_colors)
    ax_gates.set_xlim(0, 1)
    ax_gates.set_xticks([])
    for idx, passed in enumerate(gates["passed"].astype(int).tolist()):
        ax_gates.text(0.5, idx, "pass" if passed else "fail", va="center", ha="center", color="#ffffff", fontsize=8)
    ax_gates.set_title("Promotion gates")

    fig.suptitle(f"Stage574 decision: {decision['decision']}", fontsize=13)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    candidate_map: pd.DataFrame,
    annual_opportunity: pd.DataFrame,
    pairwise_corr: pd.DataFrame,
    risk_shell: pd.DataFrame,
    selector_readiness: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    material = candidate_map[candidate_map["independent_material_capacity_ok"].eq(1)].copy()
    shell_view = risk_shell[
        [
            "label_short",
            "deployable_status",
            "total_return_pct",
            "max_dd_pct",
            "ulcer_pct",
            "satellite_cumulative_pnl",
            "max_dd_delta_vs_stage526",
            "ulcer_delta_vs_stage526",
            "hold63_p10_delta_vs_stage526",
            "hold126_p10_delta_vs_stage526",
            "deployable_no_degrade_pass",
        ]
    ].copy()
    lines = [
        "# Stage276 / Stage574 低单笔风险扩池与选品晋级边界审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读审计；不修改策略、不重跑交易引擎、不生成交易候选。",
        "- 本阶段回答：低单笔风险扩池是否仍有价值，为什么当前不可晋级，下一次晋级需要什么证据。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟踪长期有效性的关键之一是跨市场分散，但分散不等于盲目增加品种；相关性、风险预算、容量和执行质量必须先于收益回测。",
        "- GitHub 上的公开趋势跟踪实现也通常把波动/风险 sizing、多市场组合和执行工程作为基础模块；本仓库不能直接复制外部框架，应该沿用 Stage526 的真实成交/保证金约束。",
        "- 本阶段因此只允许固定风险壳和点时 selector 资格闸门，不允许拿事后 top 品种做白名单。",
        "",
        "参考：",
        "",
        *[f"- {link}" for link in REFERENCE_LINKS],
        "",
        "## 晋级闸门",
        "",
        _md_table(gates),
        "",
        "## 独立候选池",
        "",
        _md_table(
            material,
            [
                "product_vt_symbol",
                "product_family",
                "total_pnl",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "positive_years",
                "abs_core_daily_pnl_corr",
                "capacity_quality_flag",
                "breadth_all_noncore_sleeve_pnl",
            ],
            max_rows=20,
        ),
        "",
        "## 年度机会",
        "",
        _md_table(
            annual_opportunity,
            ["year", "positive_count", "top6_pnl", "top6_family_count", "top6_family_max_count", "top6_products"],
            max_rows=20,
        ),
        "",
        "## 风险壳边界",
        "",
        _md_table(shell_view, max_rows=20),
        "",
        "## 候选内部相关性",
        "",
        _md_table(pairwise_corr, max_rows=20),
        "",
        "## Selector 就绪度",
        "",
        _md_table(selector_readiness, max_rows=20),
        "",
        "## 判断",
        "",
        "- 方向成立：非核心年度 top6 机会连续存在，且存在一组容量可承载、与 Stage526 日 PnL 低相关的材料性候选。",
        "- 当前不可晋级：全非核心低风险壳和上一年为正壳都没有改善 Stage526 的 DD/Ulcer/3个月/6个月左尾体验。",
        "- Stage256 upper 改善体验但属于历史白名单/上界，不是可部署 selector。",
        "- 后续只能继续累计 point-in-time 外生/舆情/库存/基差样本，达到 20/20 后按 Stage561 冻结协议做 IC、bucket 和 paper sleeve；未达标前禁止选品收益回测。",
        "",
        "## 反思",
        "",
        f"- 过拟合：`{decision['overfit_reflection']}`",
        f"- 继续价值：`{decision['continue_value_reflection']}`",
        "",
        "## 输出文件",
        "",
        f"- candidate map：`{CANDIDATE_MAP_PATH}`",
        f"- annual opportunity：`{ANNUAL_OPPORTUNITY_PATH}`",
        f"- pairwise corr：`{PAIRWISE_CORR_PATH}`",
        f"- risk shell：`{RISK_SHELL_PATH}`",
        f"- selector readiness：`{SELECTOR_READINESS_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate_map = _build_candidate_map()
    pairwise_corr = _build_pairwise_corr(candidate_map)
    annual_opportunity = _build_annual_opportunity(candidate_map)
    risk_shell = _build_risk_shell_boundary()
    selector_readiness = _build_selector_readiness()
    gates = _build_gates(candidate_map, annual_opportunity, pairwise_corr, risk_shell, selector_readiness)
    decision = _decision(candidate_map, pairwise_corr, risk_shell, selector_readiness, gates)

    candidate_map.to_csv(CANDIDATE_MAP_PATH, index=False, encoding="utf-8-sig")
    pairwise_corr.to_csv(PAIRWISE_CORR_PATH, index=False, encoding="utf-8-sig")
    annual_opportunity.to_csv(ANNUAL_OPPORTUNITY_PATH, index=False, encoding="utf-8-sig")
    risk_shell.to_csv(RISK_SHELL_PATH, index=False, encoding="utf-8-sig")
    selector_readiness.to_csv(SELECTOR_READINESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(candidate_map, annual_opportunity, pairwise_corr, risk_shell, selector_readiness, gates, decision)
    _write_report(candidate_map, annual_opportunity, pairwise_corr, risk_shell, selector_readiness, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
