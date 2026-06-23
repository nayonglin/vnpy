from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage064"
MODEL_TAG = "stage064_candidate_collision_gate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage064_c9_minrisk_candidate_collision_gate_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage064_candidate_collision_gate_audit"

FRONTIER_IN = (
    LINE_DIR
    / "outputs/stage050_route_frontier_overfit_audit/"
    "qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_frontier_metrics_"
    "stage050_route_frontier_overfit_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COLLISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_collision_matrix_{MODEL_TAG}.csv"
EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prior_evidence_rows_{MODEL_TAG}.csv"
SUPPLEMENTAL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_supplemental_evidence_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_broker_overlay_{MODEL_TAG}.png"
FRONTIER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_gate_chart_{MODEL_TAG}.png"
MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_collision_heatmap_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prior_minute_atlas_montage_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prior_minute_atlas_manifest_{MODEL_TAG}.csv"

TARGET_RETURN_RETENTION_PCT = 80.0
TARGET_DD_IMPROVEMENT_PP = 5.0
OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"


@dataclass(frozen=True)
class CurveEvidence:
    stage: str
    label: str
    curve_path: Path
    c_arm_contains: str
    color: str


@dataclass(frozen=True)
class CandidateGate:
    candidate_id: str
    label: str
    first_principle_reason: str
    external_prior: str
    closest_prior_stages: tuple[str, ...]
    structural_collision: int
    cuts_right_tail: int
    threshold_variant_risk: int
    data_coverage_blocked: int
    no_new_information: int
    should_run_true_engine_now: int
    precommit_decision: str
    next_requirement: str


CURVE_EVIDENCE = [
    CurveEvidence(
        stage="Stage008",
        label="Stage008 no-follow half risk",
        curve_path=LINE_DIR
        / "outputs/stage008_no_follow_reduce_true_engine/"
        "qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_curve_"
        "stage008_no_follow_reduce_true_engine_v1.csv",
        c_arm_contains="C_stage008",
        color="#d55e00",
    ),
    CurveEvidence(
        stage="Stage009",
        label="Stage009 opening-range hard exit",
        curve_path=LINE_DIR
        / "outputs/stage009_opening_range_adverse_exit_true_engine/"
        "qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_curve_"
        "stage009_opening_range_adverse_exit_true_engine_v1.csv",
        c_arm_contains="C_stage009",
        color="#cc3311",
    ),
    CurveEvidence(
        stage="Stage013",
        label="Stage013 min-risk clean restore",
        curve_path=LINE_DIR
        / "outputs/stage013_minrisk_clean_restore_true_engine/"
        "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_curve_"
        "stage013_minrisk_clean_restore_true_engine_v1.csv",
        c_arm_contains="C_stage013",
        color="#009e73",
    ),
    CurveEvidence(
        stage="Stage019",
        label="Stage019 no-follow light shave",
        curve_path=LINE_DIR
        / "outputs/stage019_no_follow_light_shave_true_engine/"
        "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_"
        "stage019_no_follow_light_shave_true_engine_v1.csv",
        c_arm_contains="C_stage019",
        color="#e69f00",
    ),
    CurveEvidence(
        stage="Stage046",
        label="Stage046 confirmed breakeven",
        curve_path=LINE_DIR
        / "outputs/stage046_entry_day_confirmed_breakeven_true_engine/"
        "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
        "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv",
        c_arm_contains="C_stage046",
        color="#7a3db8",
    ),
]


CANDIDATE_GATES = [
    CandidateGate(
        candidate_id="entry_day_time_stop_no_progress",
        label="Entry-day no-progress time stop",
        first_principle_reason="A high-quality breakout should work quickly; stale trades may be false starts.",
        external_prior="Time/stop rules are common risk tools, but frequent exits can create whipsaw.",
        closest_prior_stages=("Stage008", "Stage009", "Stage019"),
        structural_collision=1,
        cuts_right_tail=1,
        threshold_variant_risk=1,
        data_coverage_blocked=0,
        no_new_information=1,
        should_run_true_engine_now=0,
        precommit_decision="reject_before_true_engine",
        next_requirement="Needs a genuinely new entry-time information source; do not retest 15/30/60 minute variants.",
    ),
    CandidateGate(
        candidate_id="confirmed_breakeven_or_tight_trail",
        label="Confirmed breakeven / tight trailing stop",
        first_principle_reason="After price proves the direction, residual risk should be reduced.",
        external_prior="Trailing stops are a standard trend-following risk tool.",
        closest_prior_stages=("Stage013", "Stage046"),
        structural_collision=1,
        cuts_right_tail=1,
        threshold_variant_risk=1,
        data_coverage_blocked=0,
        no_new_information=1,
        should_run_true_engine_now=0,
        precommit_decision="reject_before_true_engine",
        next_requirement="Needs new non-price state; do not rescue with R multiples or same-day timing tweaks.",
    ),
    CandidateGate(
        candidate_id="stop_retry_reentry_candle_quality_filter",
        label="C9 reentry candle quality filter",
        first_principle_reason="A clean reclaim should show healthy microstructure before retry risk is restored.",
        external_prior="Breakout and retest workflows often use confirmation and trailing exits.",
        closest_prior_stages=("Stage054", "Stage058"),
        structural_collision=1,
        cuts_right_tail=1,
        threshold_variant_risk=1,
        data_coverage_blocked=0,
        no_new_information=1,
        should_run_true_engine_now=0,
        precommit_decision="reject_before_true_engine",
        next_requirement="Only revisit with order-book, spread, queue, or trade-flow data visible at reentry time.",
    ),
    CandidateGate(
        candidate_id="member_rank_dce_rebind",
        label="Member-rank positioning rebind",
        first_principle_reason="Large member positioning is a direct risk-absorption state, not a price-path label.",
        external_prior="Positioning data has stronger economic meaning than candle-shape filters.",
        closest_prior_stages=("Stage053", "Stage062", "Stage063"),
        structural_collision=0,
        cuts_right_tail=0,
        threshold_variant_risk=0,
        data_coverage_blocked=1,
        no_new_information=0,
        should_run_true_engine_now=0,
        precommit_decision="data_blocked_no_engine",
        next_requirement="Requires vendor/authorized/offline point-in-time history before any trading rule.",
    ),
    CandidateGate(
        candidate_id="entry_time_orderbook_liquidity_state",
        label="Entry-time orderbook/liquidity state",
        first_principle_reason="High-quality signals should enter with tolerable spread, depth, and flow imbalance.",
        external_prior="Execution quality is first-principle risk control, but must be point-in-time and independent.",
        closest_prior_stages=("Stage045", "Stage051"),
        structural_collision=0,
        cuts_right_tail=0,
        threshold_variant_risk=0,
        data_coverage_blocked=1,
        no_new_information=0,
        should_run_true_engine_now=0,
        precommit_decision="allowed_direction_data_first",
        next_requirement="Collect or locate point-in-time bid/ask/depth/trade-flow data, then run a fixed-spec read-only audit.",
    ),
]


ATLAS_SOURCES = [
    (
        "Stage008 no-follow atlas",
        LINE_DIR
        / "outputs/stage008_no_follow_reduce_true_engine/"
        "qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_atlas_page001_"
        "stage008_no_follow_reduce_true_engine_v1.png",
    ),
    (
        "Stage009 hard-exit atlas",
        LINE_DIR
        / "outputs/stage009_opening_range_adverse_exit_true_engine/"
        "qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_atlas_page001_"
        "stage009_opening_range_adverse_exit_true_engine_v1.png",
    ),
    (
        "Stage013 min-risk atlas",
        LINE_DIR
        / "outputs/stage013_minrisk_clean_restore_true_engine/"
        "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_atlas_page001_"
        "stage013_minrisk_clean_restore_true_engine_v1.png",
    ),
    (
        "Stage046 breakeven atlas",
        LINE_DIR
        / "outputs/stage046_entry_day_confirmed_breakeven_true_engine/"
        "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_atlas_page001_"
        "stage046_entry_day_confirmed_breakeven_true_engine_v1.png",
    ),
    (
        "Stage054 reentry atlas",
        LINE_DIR
        / "outputs/stage054_c9_reentry_reclaim_quality_audit/"
        "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_atlas_page001_"
        "stage054_c9_reentry_reclaim_quality_audit_v1.png",
    ),
    (
        "Stage058 single-bar atlas",
        LINE_DIR
        / "outputs/stage058_reentry_full_ohlcv_integration_audit/"
        "qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_single_bar_atlas_"
        "stage058_reentry_full_ohlcv_integration_audit_v1.png",
    ),
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _format_float(value: object, digits: int = 4) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value):,.{digits}f}"
    except Exception:
        return str(value)


def _stage_prior_rows(frontier: pd.DataFrame, stages: Iterable[str]) -> pd.DataFrame:
    stages = set(stages)
    return frontier[frontier["stage"].astype(str).isin(stages)].copy()


def _build_candidate_records(frontier: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for gate in CANDIDATE_GATES:
        prior = _stage_prior_rows(frontier, gate.closest_prior_stages)
        if prior.empty:
            best_retention = np.nan
            best_dd_improvement = np.nan
            worst_broker_worse = np.nan
            true_engine_prior_count = 0
            strict_pass_count = 0
            prior_labels = ""
        else:
            best_retention = prior["return_retention_pct"].max()
            best_dd_improvement = prior["dd_improvement_pp"].max()
            worst_broker_worse = prior["broker10_worse_pp"].max()
            true_engine_prior_count = int((prior["evidence_type"].astype(str) == "true_engine").sum())
            strict_pass_count = int(prior["strict_candidate_pass"].fillna(False).astype(bool).sum())
            prior_labels = "; ".join(
                f"{row.stage}:{row.label}" for row in prior[["stage", "label"]].itertuples(index=False)
            )
        records.append(
            {
                "candidate_id": gate.candidate_id,
                "label": gate.label,
                "first_principle_reason": gate.first_principle_reason,
                "external_prior": gate.external_prior,
                "closest_prior_stages": ",".join(gate.closest_prior_stages),
                "prior_labels": prior_labels,
                "true_engine_prior_count": true_engine_prior_count,
                "strict_pass_count": strict_pass_count,
                "best_prior_return_retention_pct": best_retention,
                "best_prior_dd_improvement_pp": best_dd_improvement,
                "worst_prior_broker10_worse_pp": worst_broker_worse,
                "structural_collision": gate.structural_collision,
                "cuts_right_tail": gate.cuts_right_tail,
                "threshold_variant_risk": gate.threshold_variant_risk,
                "data_coverage_blocked": gate.data_coverage_blocked,
                "no_new_information": gate.no_new_information,
                "should_run_true_engine_now": bool(gate.should_run_true_engine_now),
                "precommit_decision": gate.precommit_decision,
                "next_requirement": gate.next_requirement,
            }
        )
    return pd.DataFrame(records)


def _build_supplemental_evidence() -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    stage051_path = (
        LINE_DIR
        / "outputs/stage051_entry_execution_shortfall_audit/"
        "qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_summary_"
        "stage051_entry_execution_shortfall_audit_v1.csv"
    )
    if stage051_path.exists():
        row = _read_csv(stage051_path).iloc[0].to_dict()
        rows.append(
            {
                "stage": "Stage051",
                "evidence_key": "entry_execution_shortfall",
                "evidence_type": "upper_bound",
                "decision": row.get("decision"),
                "metric_1": "target_net_pnl",
                "value_1": row.get("target_net_pnl"),
                "metric_2": "upper_bound_return_retention_pct",
                "value_2": row.get("upper_bound_return_retention_pct"),
                "metric_3": "upper_bound_max_dd_improvement_pp",
                "value_3": row.get("upper_bound_max_dd_improvement_pp"),
                "interpretation": "Adverse entry gap is right-tail-bearing; execution state alone is not a skip rule.",
                "source_path": str(stage051_path),
            }
        )

    stage053_path = (
        LINE_DIR
        / "outputs/stage053_external_source_priority_audit/"
        "qmt_roll_stage053_c9_minrisk_external_source_priority_audit_route_summary_"
        "stage053_external_source_priority_audit_v1.csv"
    )
    if stage053_path.exists():
        df = _read_csv(stage053_path)
        for row in df.to_dict("records"):
            rows.append(
                {
                    "stage": "Stage053",
                    "evidence_key": row.get("source_key"),
                    "evidence_type": "external_source_upper_bound",
                    "decision": row.get("data_priority"),
                    "metric_1": "ready_pct",
                    "value_1": row.get("ready_pct"),
                    "metric_2": "upper_bound_return_retention_pct",
                    "value_2": row.get("upper_bound_return_retention_pct"),
                    "metric_3": "upper_bound_dd_improvement_pp",
                    "value_3": row.get("upper_bound_dd_improvement_pp"),
                    "interpretation": row.get("next_data_action"),
                    "source_path": str(stage053_path),
                }
            )

    stage054_path = (
        LINE_DIR
        / "outputs/stage054_c9_reentry_reclaim_quality_audit/"
        "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_decision_"
        "stage054_c9_reentry_reclaim_quality_audit_v1.json"
    )
    if stage054_path.exists():
        data = json.loads(stage054_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "stage": "Stage054",
                "evidence_key": "slow_or_deep_reentry",
                "evidence_type": "upper_bound",
                "decision": data.get("decision"),
                "metric_1": "target_reentry_lot_pnl",
                "value_1": data.get("target", {}).get("target_reentry_lot_pnl"),
                "metric_2": "upper_bound_return_retention_pct",
                "value_2": data.get("upper_bound", {}).get("return_retention_pct"),
                "metric_3": "upper_bound_dd_improvement_pp",
                "value_3": data.get("upper_bound", {}).get("dd_improvement_pp"),
                "interpretation": "Slow/deep reentry target is net positive and worsens drawdown when skipped.",
                "source_path": str(stage054_path),
            }
        )

    stage058_path = (
        LINE_DIR
        / "outputs/stage058_reentry_full_ohlcv_integration_audit/"
        "qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_decision_"
        "stage058_reentry_full_ohlcv_integration_audit_v1.json"
    )
    if stage058_path.exists():
        data = json.loads(stage058_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "stage": "Stage058",
                "evidence_key": "full_reentry_ohlcv",
                "evidence_type": "data_asset_no_rule",
                "decision": data.get("decision"),
                "metric_1": "full_ready_event_count",
                "value_1": data.get("full_ready_event_count"),
                "metric_2": "integrated_reentry_pnl",
                "value_2": data.get("integrated_reentry_pnl"),
                "metric_3": "max_abs_spearman_feature_pnl",
                "value_3": data.get("max_abs_spearman_feature_pnl"),
                "interpretation": data.get("judgment"),
                "source_path": str(stage058_path),
            }
        )

    stage062_path = (
        LINE_DIR
        / "outputs/stage062_member_rank_dce_alt_route_audit/"
        "qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_summary_"
        "stage062_member_rank_dce_alt_route_audit_v1.csv"
    )
    if stage062_path.exists():
        row = _read_csv(stage062_path).iloc[0].to_dict()
        rows.append(
            {
                "stage": "Stage062",
                "evidence_key": "member_rank_dce_alt_routes",
                "evidence_type": "data_repair_blocked",
                "decision": "stage062_dce_alternative_routes_blocked_no_strategy_rule",
                "metric_1": "member_ready_rate_pct",
                "value_1": row.get("member_ready_rate_pct"),
                "metric_2": "member_missing_net_pnl",
                "value_2": row.get("member_missing_net_pnl"),
                "metric_3": "dce_alt_route_ok_with_target_hit",
                "value_3": row.get("dce_alt_route_ok_with_target_hit"),
                "interpretation": "Member-rank economics remain interesting but DCE/public historical coverage is blocked.",
                "source_path": str(stage062_path),
            }
        )

    stage063_path = (
        LINE_DIR
        / "outputs/stage063_dce_official_http_direct_audit/"
        "qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit_summary_"
        "stage063_dce_official_http_direct_audit_v1.csv"
    )
    if stage063_path.exists():
        row = _read_csv(stage063_path).iloc[0].to_dict()
        rows.append(
            {
                "stage": "Stage063",
                "evidence_key": "dce_official_http_direct",
                "evidence_type": "data_repair_blocked",
                "decision": row.get("decision"),
                "metric_1": "data_ready_count",
                "value_1": row.get("data_ready_count"),
                "metric_2": "dce_member_missing_net_pnl",
                "value_2": row.get("dce_member_missing_net_pnl"),
                "metric_3": "direct_repair_ready",
                "value_3": row.get("direct_repair_ready"),
                "interpretation": row.get("next_action"),
                "source_path": str(stage063_path),
            }
        )

    return pd.DataFrame(rows)


def _select_arm(df: pd.DataFrame, contains: str) -> pd.DataFrame:
    arm_cols = [col for col in ("arm", "arm_key", "variant") if col in df.columns]
    if not arm_cols:
        raise ValueError("No arm-like column found in curve file")
    mask = pd.Series(False, index=df.index)
    for col in arm_cols:
        mask = mask | df[col].astype(str).str.contains(contains, na=False)
    out = df.loc[mask].copy()
    if out.empty:
        raise ValueError(f"No curve rows matching {contains}")
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date")


def _select_official_arm(df: pd.DataFrame) -> pd.DataFrame:
    arm_cols = [col for col in ("arm", "arm_key", "variant") if col in df.columns]
    mask = pd.Series(False, index=df.index)
    for col in arm_cols:
        values = df[col].astype(str)
        mask = mask | values.str.contains("A_official", na=False)
        mask = mask | values.str.contains("official_live_stage847_c9_15w", na=False)
    out = df.loc[mask].copy()
    if out.empty:
        raise ValueError("No official curve rows found")
    out["date"] = pd.to_datetime(out["date"])
    return out.sort_values("date")


def _plot_path_overlay() -> None:
    first_df = _read_csv(CURVE_EVIDENCE[0].curve_path)
    official = _select_official_arm(first_df)

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    axes[0].plot(
        official["date"],
        official["account_equity"] / 1_000_000,
        label=f"A official {OFFICIAL_LIVE_ALIAS}",
        color="#0072b2",
        linewidth=2.2,
    )
    axes[1].plot(official["date"], official["drawdown_pct"], color="#0072b2", linewidth=2.0)
    axes[2].plot(official["date"], official["broker10_margin_to_equity_pct"], color="#0072b2", linewidth=2.0)

    for spec in CURVE_EVIDENCE:
        df = _read_csv(spec.curve_path)
        curve = _select_arm(df, spec.c_arm_contains)
        axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, label=spec.label, color=spec.color, alpha=0.86)
        axes[1].plot(curve["date"], curve["drawdown_pct"], color=spec.color, alpha=0.86)
        axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color=spec.color, alpha=0.86)

    axes[0].set_title("Stage064 prior minute-rule collision: equity paths")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8, ncol=2)

    official_max_dd = float(official["drawdown_pct"].min())
    axes[1].axhline(official_max_dd, color="#0072b2", linestyle=":", linewidth=1.2, label="official max DD")
    axes[1].axhline(official_max_dd + TARGET_DD_IMPROVEMENT_PP, color="#008000", linestyle="--", linewidth=1.2, label="5pp DD target")
    axes[1].set_title("Drawdown: prior variants do not clear the drawdown-retention gate")
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="lower left", fontsize=8)

    axes[2].axhline(100.0, color="#cc3311", linestyle="--", linewidth=1.2, label="broker10 100%")
    axes[2].set_title("Broker10 pressure: many defensive variants worsen margin pressure")
    axes[2].set_ylabel("Broker10 margin/equity %")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="upper left", fontsize=8)

    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_frontier(frontier: pd.DataFrame, candidate_records: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(
        frontier["return_retention_pct"],
        frontier["dd_improvement_pp"],
        s=46,
        color="#999999",
        alpha=0.55,
        label="prior tested route",
    )
    used_stages = set()
    for stages in candidate_records["closest_prior_stages"].astype(str):
        used_stages.update(stage for stage in stages.split(",") if stage)
    used = frontier[frontier["stage"].astype(str).isin(used_stages)].copy()
    ax.scatter(
        used["return_retention_pct"],
        used["dd_improvement_pp"],
        s=82,
        color="#d55e00",
        edgecolor="black",
        linewidth=0.6,
        label="evidence used by Stage064",
    )
    for row in used.itertuples(index=False):
        ax.annotate(str(row.stage), (row.return_retention_pct, row.dd_improvement_pp), fontsize=8, xytext=(4, 4), textcoords="offset points")
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    ax.fill_between(
        [TARGET_RETURN_RETENTION_PCT, max(110.0, x_max)],
        TARGET_DD_IMPROVEMENT_PP,
        max(8.0, y_max),
        color="#009e73",
        alpha=0.12,
        label="required gate region",
    )
    ax.axvline(TARGET_RETURN_RETENTION_PCT, color="#009e73", linestyle="--", linewidth=1.2)
    ax.axhline(TARGET_DD_IMPROVEMENT_PP, color="#009e73", linestyle="--", linewidth=1.2)
    ax.set_title("Stage064 precommit gate: no prior collision route reached the target region")
    ax.set_xlabel("Return retention vs official (%)")
    ax.set_ylabel("Max drawdown improvement vs official (pp)")
    ax.grid(alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(FRONTIER_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_collision_heatmap(candidate_records: pd.DataFrame) -> None:
    cols = [
        "structural_collision",
        "cuts_right_tail",
        "threshold_variant_risk",
        "data_coverage_blocked",
        "no_new_information",
        "should_run_true_engine_now",
    ]
    matrix = candidate_records[cols].astype(int).to_numpy()
    fig, ax = plt.subplots(figsize=(12, 6.4))
    im = ax.imshow(matrix, cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=28, ha="right")
    ax.set_yticks(np.arange(len(candidate_records)))
    ax.set_yticklabels(candidate_records["candidate_id"].tolist())
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", color="black", fontsize=9)
    ax.set_title("Stage064 candidate collision heatmap (1 means active gate)")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(MATRIX_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_atlas_montage() -> pd.DataFrame:
    manifest_rows = []
    available = [(title, path) for title, path in ATLAS_SOURCES if path.exists()]
    for title, path in ATLAS_SOURCES:
        manifest_rows.append({"title": title, "path": str(path), "exists": path.exists()})
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    if not available:
        return manifest

    n = len(available)
    cols = 2
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(14, rows * 4.6))
    axes_arr = np.asarray(axes).reshape(-1)
    for ax, (title, path) in zip(axes_arr, available):
        img = mpimg.imread(path)
        ax.imshow(img)
        ax.set_title(title, fontsize=10)
        ax.axis("off")
    for ax in axes_arr[len(available) :]:
        ax.axis("off")
    fig.suptitle("Stage064 reused minute atlas evidence: old variants already collide with right-tail protection", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(ATLAS_OUT, dpi=140)
    plt.close(fig)
    return manifest


def _write_report(
    candidate_records: pd.DataFrame,
    prior_evidence: pd.DataFrame,
    supplemental_evidence: pd.DataFrame,
) -> None:
    decision = "stage064_reject_colliding_minute_stop_variants_require_new_information"
    lines = [
        f"# {STAGE} Candidate Collision Gate Audit",
        "",
        f"- Created: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"- Official baseline: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- Decision: `{decision}`",
        "- This stage is a precommit gate, not a new trading engine and not an A/B promotion test.",
        "",
        "## External research conclusion",
        "",
        "- Trend-following systems are path-dependent; robustness should be evaluated across changing market regimes.",
        "- Stop, trailing-stop, and time-stop concepts are common risk controls, but prior literature and practice warn that frequent exits can whipsaw trend systems.",
        "- GitHub examples commonly implement trailing exits and direction-flip exits, but that is a pattern catalogue, not evidence that the pattern fits this C9 right-tail distribution.",
        "",
        "## Candidate Gate",
        "",
        candidate_records[
            [
                "candidate_id",
                "precommit_decision",
                "closest_prior_stages",
                "best_prior_return_retention_pct",
                "best_prior_dd_improvement_pp",
                "should_run_true_engine_now",
            ]
        ].to_markdown(index=False),
        "",
        "## Prior Evidence Rows",
        "",
        prior_evidence[
            [
                "stage",
                "label",
                "route_family",
                "evidence_type",
                "return_retention_pct",
                "dd_improvement_pp",
                "broker10_worse_pp",
                "strict_candidate_pass",
                "primary_failure_reason",
            ]
        ].to_markdown(index=False),
        "",
        "## Supplemental Evidence",
        "",
        supplemental_evidence[
            [
                "stage",
                "evidence_key",
                "evidence_type",
                "decision",
                "metric_1",
                "value_1",
                "metric_2",
                "value_2",
                "metric_3",
                "value_3",
            ]
        ].to_markdown(index=False),
        "",
        "## Outputs",
        "",
        f"- Collision CSV: `{COLLISION_OUT}`",
        f"- Prior evidence CSV: `{EVIDENCE_OUT}`",
        f"- Supplemental evidence CSV: `{SUPPLEMENTAL_OUT}`",
        f"- Equity/drawdown/broker chart: `{PATH_CHART_OUT}`",
        f"- Frontier chart: `{FRONTIER_CHART_OUT}`",
        f"- Collision heatmap: `{MATRIX_CHART_OUT}`",
        f"- Prior minute atlas montage: `{ATLAS_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frontier = _read_csv(FRONTIER_IN)
    candidate_records = _build_candidate_records(frontier)
    used_stages = set()
    for stages in candidate_records["closest_prior_stages"].astype(str):
        used_stages.update(stage for stage in stages.split(",") if stage)
    prior_evidence = _stage_prior_rows(frontier, used_stages)

    candidate_records.to_csv(COLLISION_OUT, index=False, encoding="utf-8-sig")
    prior_evidence.to_csv(EVIDENCE_OUT, index=False, encoding="utf-8-sig")
    supplemental_evidence = _build_supplemental_evidence()
    supplemental_evidence.to_csv(SUPPLEMENTAL_OUT, index=False, encoding="utf-8-sig")

    _plot_path_overlay()
    _plot_frontier(frontier, candidate_records)
    _plot_collision_heatmap(candidate_records)
    atlas_manifest = _plot_atlas_montage()

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "line_id": LINE_ID,
                "model_tag": MODEL_TAG,
                "created_at": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "decision": "stage064_reject_colliding_minute_stop_variants_require_new_information",
                "strategy_rule_created": False,
                "true_engine_run": False,
                "ab_triggered": False,
                "candidate_count": int(len(candidate_records)),
                "should_run_true_engine_now_count": int(candidate_records["should_run_true_engine_now"].sum()),
                "reject_before_true_engine_count": int(
                    (candidate_records["precommit_decision"] == "reject_before_true_engine").sum()
                ),
                "data_blocked_or_data_first_count": int(
                    candidate_records["precommit_decision"].isin(
                        ["data_blocked_no_engine", "allowed_direction_data_first"]
                    ).sum()
                ),
                "prior_evidence_row_count": int(len(prior_evidence)),
                "supplemental_evidence_row_count": int(len(supplemental_evidence)),
                "prior_strict_candidate_pass_count": int(
                    prior_evidence["strict_candidate_pass"].fillna(False).astype(bool).sum()
                ),
                "atlas_source_count": int(len(atlas_manifest)),
                "atlas_source_exists_count": int(atlas_manifest["exists"].sum()),
                "target_return_retention_pct": TARGET_RETURN_RETENTION_PCT,
                "target_dd_improvement_pp": TARGET_DD_IMPROVEMENT_PP,
                "next_allowed_route": "point_in_time_orderbook_or_authorized_positioning_data_then_fixed_spec_readonly_audit",
            }
        ]
    )
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")

    decision = summary.iloc[0].to_dict()
    decision["outputs"] = {
        "summary": str(SUMMARY_OUT),
        "candidate_collision_matrix": str(COLLISION_OUT),
        "prior_evidence_rows": str(EVIDENCE_OUT),
        "supplemental_evidence": str(SUPPLEMENTAL_OUT),
        "report": str(REPORT_OUT),
        "path_drawdown_broker_overlay": str(PATH_CHART_OUT),
        "frontier_gate_chart": str(FRONTIER_CHART_OUT),
        "collision_heatmap": str(MATRIX_CHART_OUT),
        "prior_minute_atlas_montage": str(ATLAS_OUT),
        "prior_minute_atlas_manifest": str(ATLAS_MANIFEST_OUT),
    }
    DECISION_OUT.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(candidate_records, prior_evidence, supplemental_evidence)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
