from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage050"
MODEL_TAG = "stage050_route_frontier_overfit_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage050_route_frontier_overfit_audit"

FRONTIER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_metrics_{MODEL_TAG}.csv"
ROUTE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_family_summary_{MODEL_TAG}.csv"
NEXT_ROUTE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_route_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_drawdown_frontier_{MODEL_TAG}.png"
PATH_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_representative_path_chart_{MODEL_TAG}.png"
FAILURE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_failure_reason_chart_{MODEL_TAG}.png"

OFFICIAL_RETURN_COL = "official_total_return_pct"
OFFICIAL_DD_COL = "official_max_dd_pct"
OFFICIAL_BROKER_COL = "official_broker10_peak_pct"
TARGET_RETURN_RETENTION = 80.0
TARGET_DD_IMPROVEMENT = 5.0
EPS = 1e-6


@dataclass(frozen=True)
class TwoArmSpec:
    stage: str
    route_family: str
    evidence_type: str
    path: Path
    verdict: str
    route_note: str


@dataclass(frozen=True)
class MetricsSpec:
    stage: str
    route_family: str
    evidence_type: str
    path: Path
    verdict: str
    route_note: str
    official_variant_values: tuple[str, ...]
    variant_col: str = "variant"


@dataclass(frozen=True)
class UpperBoundSpec:
    stage: str
    route_family: str
    evidence_type: str
    path: Path
    verdict: str
    route_note: str
    candidate_label: str


@dataclass(frozen=True)
class CurveSpec:
    label: str
    path: Path
    equity_col: str
    drawdown_col: str
    filter_col: str | None = None
    filter_value: str | None = None
    line_style: str = "-"
    evidence_type: str = ""


TWO_ARM_SPECS = [
    TwoArmSpec(
        stage="Stage002",
        route_family="minute_scout_restore",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage002_delayed_restore_true_engine/"
        "qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_summary_"
        "stage002_delayed_restore_true_engine_v1.csv",
        verdict="closed_failed_retention_and_broker",
        route_note="50% scout then +0.5R restore cut right-tail compounding.",
    ),
    TwoArmSpec(
        stage="Stage003",
        route_family="margin_survival_deleverage",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage003_forced_margin_survival/"
        "qmt_roll_stage003_c9_minrisk_forced_margin_survival_summary_"
        "stage003_forced_margin_survival_v1.csv",
        verdict="closed_failed_retention_dd_and_broker",
        route_note="Forced margin deleverage is a lagging cut of large winners.",
    ),
    TwoArmSpec(
        stage="Stage004",
        route_family="minute_scout_restore",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage004_cap_only_delayed_restore/"
        "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_summary_"
        "stage004_cap_only_delayed_restore_v1.csv",
        verdict="closed_failed_retention_dd_and_broker",
        route_note="Restricting restore to broker10 cap events still cut right-tail base.",
    ),
    TwoArmSpec(
        stage="Stage008",
        route_family="minute_reduce_after_no_follow",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage008_no_follow_reduce_true_engine/"
        "qmt_roll_stage008_c9_minrisk_no_follow_reduce_true_engine_summary_"
        "stage008_no_follow_reduce_true_engine_v1.csv",
        verdict="closed_failed_retention_dd_and_broker",
        route_note="No-follow direct half-risk cut damaged equity denominator.",
    ),
    TwoArmSpec(
        stage="Stage009",
        route_family="minute_hard_exit",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage009_opening_range_adverse_exit_true_engine/"
        "qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_summary_"
        "stage009_opening_range_adverse_exit_true_engine_v1.csv",
        verdict="closed_failed_return_retention",
        route_note="Opening-range adverse break reduced drawdown but cut most right-tail return.",
    ),
    TwoArmSpec(
        stage="Stage013",
        route_family="minute_minrisk_restore",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage013_minrisk_clean_restore_true_engine/"
        "qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_summary_"
        "stage013_minrisk_clean_restore_true_engine_v1.csv",
        verdict="closed_failed_retention_dd_and_broker",
        route_note="One-lot scout then clean30 restore missed the right-tail too long.",
    ),
    TwoArmSpec(
        stage="Stage019",
        route_family="minute_reduce_after_no_follow",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage019_no_follow_light_shave_true_engine/"
        "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_summary_"
        "stage019_no_follow_light_shave_true_engine_v1.csv",
        verdict="closed_failed_retention_dd_and_broker",
        route_note="80% light shave still failed retention and worsened drawdown.",
    ),
    TwoArmSpec(
        stage="Stage046",
        route_family="minute_confirmed_breakeven",
        evidence_type="true_engine",
        path=LINE_DIR
        / "outputs/stage046_entry_day_confirmed_breakeven_true_engine/"
        "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_summary_"
        "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv",
        verdict="closed_failed_retention_dd_and_broker",
        route_note="Entry-day confirmed breakeven cut normal trend volatility and right-tail.",
    ),
]

METRICS_SPECS = [
    MetricsSpec(
        stage="Stage017",
        route_family="account_overlay",
        evidence_type="proxy",
        path=LINE_DIR
        / "outputs/stage017_account_layer_cppi_tipp_audit/"
        "qmt_roll_stage017_c9_minrisk_account_layer_cppi_tipp_audit_metrics_"
        "stage017_account_layer_cppi_tipp_audit_v1.csv",
        verdict="closed_proxy_boundary_not_candidate",
        route_note="CPPI/TIPP/fixed cash reserve shows the return-drawdown tradeoff boundary.",
        official_variant_values=("A_official_c9_15w",),
    ),
    MetricsSpec(
        stage="Stage018",
        route_family="daily_quality_proxy",
        evidence_type="proxy",
        path=LINE_DIR
        / "outputs/stage018_quality_conditioned_risk_shave_proxy/"
        "qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_metrics_"
        "stage018_quality_conditioned_risk_shave_proxy_v1.csv",
        verdict="proxy_only_true_engine_later_failed",
        route_note="Best daily proxy was later falsified by Stage019 true engine.",
        official_variant_values=("A_official_c9_15w",),
    ),
    MetricsSpec(
        stage="Stage020",
        route_family="account_profit_tranche",
        evidence_type="proxy",
        path=LINE_DIR
        / "outputs/stage020_balanced_tranche_profit_lock_proxy/"
        "qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_metrics_"
        "stage020_balanced_tranche_profit_lock_proxy_v1.csv",
        verdict="closed_failed_return_retention",
        route_note="Profit lock reduced total-wealth drawdown but suppressed compounding.",
        official_variant_values=("A_official_full_reinvest",),
        variant_col="arm",
    ),
    MetricsSpec(
        stage="Stage021",
        route_family="correlation_crowding_proxy",
        evidence_type="proxy",
        path=LINE_DIR
        / "outputs/stage021_same_direction_correlation_crowding_proxy/"
        "qmt_roll_stage021_c9_minrisk_same_direction_correlation_crowding_proxy_metrics_"
        "stage021_same_direction_correlation_crowding_proxy_v1.csv",
        verdict="closed_proxy_no_candidate",
        route_note="Same-direction correlation affected too few lots and worsened drawdown.",
        official_variant_values=("A_official_c9_15w",),
    ),
]

UPPER_BOUND_SPECS = [
    UpperBoundSpec(
        stage="Stage048",
        route_family="preentry_vol_participation",
        evidence_type="upper_bound",
        path=LINE_DIR
        / "outputs/stage048_lowvol_lowparticipation_robustness_audit/"
        "qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_summary_"
        "stage048_lowvol_lowparticipation_robustness_audit_v1.csv",
        verdict="closed_upper_bound_too_small",
        route_note="Perfect skip of the target cohort repaired only 0.163pp of max drawdown.",
        candidate_label="upper_bound_skip_lowvol_lowparticipation",
    ),
    UpperBoundSpec(
        stage="Stage049",
        route_family="product_trend_tstat",
        evidence_type="upper_bound",
        path=LINE_DIR
        / "outputs/stage049_product_trend_tstat_preentry_audit/"
        "qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_summary_"
        "stage049_product_trend_tstat_preentry_audit_v1.csv",
        verdict="closed_data_coverage_and_dd_worse",
        route_note="Trend t-stat ready coverage was only 6.5%, and perfect skip worsened drawdown.",
        candidate_label="upper_bound_skip_no_significant_aligned_trend",
    ),
]

CURVE_SPECS = [
    CurveSpec(
        label="Official C9/15w",
        path=LINE_DIR
        / "outputs/stage002_delayed_restore_true_engine/"
        "qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_curve_"
        "stage002_delayed_restore_true_engine_v1.csv",
        equity_col="account_equity",
        drawdown_col="drawdown_pct",
        filter_col="arm",
        filter_value="A_official_stage847_c9_15w",
        line_style="-",
        evidence_type="official",
    ),
    CurveSpec(
        label="Stage009 true: opening-range exit",
        path=LINE_DIR
        / "outputs/stage009_opening_range_adverse_exit_true_engine/"
        "qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_curve_"
        "stage009_opening_range_adverse_exit_true_engine_v1.csv",
        equity_col="account_equity",
        drawdown_col="drawdown_pct",
        filter_col="arm",
        filter_value="C_stage009_opening_range_adverse_exit",
        line_style="-",
        evidence_type="true_engine",
    ),
    CurveSpec(
        label="Stage018 proxy: no-follow 80%",
        path=LINE_DIR
        / "outputs/stage018_quality_conditioned_risk_shave_proxy/"
        "qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_curves_"
        "stage018_quality_conditioned_risk_shave_proxy_v1.csv",
        equity_col="overlay_equity",
        drawdown_col="overlay_drawdown_pct",
        filter_col="variant",
        filter_value="no_follow_30m_low_quality_80",
        line_style="--",
        evidence_type="proxy",
    ),
    CurveSpec(
        label="Stage020 proxy: profit tranche",
        path=LINE_DIR
        / "outputs/stage020_balanced_tranche_profit_lock_proxy/"
        "qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy_ledger_"
        "stage020_balanced_tranche_profit_lock_proxy_v1.csv",
        equity_col="total_equity",
        drawdown_col="total_drawdown_pct",
        filter_col="arm",
        filter_value="balanced_tranche_v1_c9_15w_stage232_reuse",
        line_style="--",
        evidence_type="proxy",
    ),
    CurveSpec(
        label="Stage048 upper: low-vol low-part",
        path=LINE_DIR
        / "outputs/stage048_lowvol_lowparticipation_robustness_audit/"
        "qmt_roll_stage048_c9_minrisk_lowvol_lowparticipation_robustness_audit_upper_bound_curve_"
        "stage048_lowvol_lowparticipation_robustness_audit_v1.csv",
        equity_col="upper_bound_skip_target_equity",
        drawdown_col="upper_bound_drawdown_pct",
        line_style=":",
        evidence_type="upper_bound",
    ),
    CurveSpec(
        label="Stage049 upper: trend t-stat",
        path=LINE_DIR
        / "outputs/stage049_product_trend_tstat_preentry_audit/"
        "qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_upper_bound_curve_"
        "stage049_product_trend_tstat_preentry_audit_v1.csv",
        equity_col="upper_bound_skip_target_equity",
        drawdown_col="upper_bound_drawdown_pct",
        line_style=":",
        evidence_type="upper_bound",
    ),
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return out if np.isfinite(out) else float("nan")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _find_official_row(frame: pd.DataFrame, official_values: tuple[str, ...] | None = None) -> pd.Series:
    if official_values:
        for col in ("variant", "arm"):
            if col in frame.columns:
                mask = frame[col].astype(str).isin(official_values)
                if mask.any():
                    return frame.loc[mask].iloc[0]
    for col in ("arm", "variant", "arm_key", "label"):
        if col in frame.columns:
            mask = frame[col].astype(str).str.contains("official|A_official", case=False, regex=True, na=False)
            if mask.any():
                return frame.loc[mask].iloc[0]
    return frame.iloc[0]


def _is_official_row(row: pd.Series, official: pd.Series, variant_col: str = "variant") -> bool:
    if variant_col in row.index and variant_col in official.index:
        return str(row[variant_col]) == str(official[variant_col])
    if "arm" in row.index and "arm" in official.index:
        return str(row["arm"]) == str(official["arm"])
    return False


def _base_record(
    *,
    stage: str,
    label: str,
    route_family: str,
    evidence_type: str,
    verdict: str,
    route_note: str,
    end_equity: float,
    total_return_pct: float,
    return_retention_pct: float,
    max_dd_pct: float,
    dd_improvement_pp: float,
    sharpe: float,
    broker10_peak_pct: float,
    official_return_pct: float,
    official_max_dd_pct: float,
    official_sharpe: float,
    official_broker10_peak_pct: float,
    source_path: Path,
) -> dict[str, Any]:
    return_80_pass = return_retention_pct + EPS >= TARGET_RETURN_RETENTION
    dd5_pass = dd_improvement_pp + EPS >= TARGET_DD_IMPROVEMENT
    broker10_not_worse = (
        np.isnan(broker10_peak_pct)
        or np.isnan(official_broker10_peak_pct)
        or broker10_peak_pct <= official_broker10_peak_pct + 1e-9
    )
    sharpe_not_worse = np.isnan(sharpe) or np.isnan(official_sharpe) or sharpe >= official_sharpe - 0.05
    metric_target_pass = bool(return_80_pass and dd5_pass and broker10_not_worse and sharpe_not_worse)
    deployable_evidence_pass = evidence_type == "true_engine"
    strict_candidate_pass = bool(metric_target_pass and deployable_evidence_pass)
    failure_reasons: list[str] = []
    if not return_80_pass:
        failure_reasons.append("return_retention_lt80")
    if not dd5_pass:
        failure_reasons.append("dd_improvement_lt5pp")
    if not broker10_not_worse:
        failure_reasons.append("broker10_worse")
    if not sharpe_not_worse:
        failure_reasons.append("sharpe_lower")
    if evidence_type != "true_engine":
        failure_reasons.append(f"{evidence_type}_not_deployable")
    if not failure_reasons:
        failure_reasons.append("none")
    return {
        "stage": stage,
        "label": label,
        "route_family": route_family,
        "evidence_type": evidence_type,
        "verdict": verdict,
        "route_note": route_note,
        "end_equity": end_equity,
        "total_return_pct": total_return_pct,
        "return_retention_pct": return_retention_pct,
        "max_dd_pct": max_dd_pct,
        "dd_improvement_pp": dd_improvement_pp,
        "sharpe": sharpe,
        "broker10_peak_pct": broker10_peak_pct,
        "official_total_return_pct": official_return_pct,
        "official_max_dd_pct": official_max_dd_pct,
        "official_sharpe": official_sharpe,
        "official_broker10_peak_pct": official_broker10_peak_pct,
        "return_80_pass": return_80_pass,
        "dd5_pass": dd5_pass,
        "broker10_not_worse": broker10_not_worse,
        "sharpe_not_worse": sharpe_not_worse,
        "metric_target_pass": metric_target_pass,
        "deployable_evidence_pass": deployable_evidence_pass,
        "strict_candidate_pass": strict_candidate_pass,
        "primary_failure_reason": failure_reasons[0],
        "failure_reasons": ";".join(failure_reasons),
        "source_path": str(source_path),
    }


def _records_from_two_arm(spec: TwoArmSpec) -> list[dict[str, Any]]:
    frame = _read_csv(spec.path)
    official = _find_official_row(frame)
    official_return = _safe_float(official.get("total_return_pct"))
    official_dd = _safe_float(official.get("max_dd_pct"))
    official_sharpe = _safe_float(official.get("sharpe"))
    official_broker = _safe_float(official.get("max_broker10_margin_to_equity_pct"))
    records = []
    for _, row in frame.iterrows():
        if _is_official_row(row, official):
            continue
        total_return = _safe_float(row.get("total_return_pct"))
        max_dd = _safe_float(row.get("max_dd_pct"))
        return_retention = total_return / official_return * 100.0 if official_return else float("nan")
        dd_improvement = max_dd - official_dd
        label = str(row.get("arm", row.get("variant", spec.stage)))
        records.append(
            _base_record(
                stage=spec.stage,
                label=label,
                route_family=spec.route_family,
                evidence_type=spec.evidence_type,
                verdict=spec.verdict,
                route_note=spec.route_note,
                end_equity=_safe_float(row.get("end_equity")),
                total_return_pct=total_return,
                return_retention_pct=return_retention,
                max_dd_pct=max_dd,
                dd_improvement_pp=dd_improvement,
                sharpe=_safe_float(row.get("sharpe")),
                broker10_peak_pct=_safe_float(row.get("max_broker10_margin_to_equity_pct")),
                official_return_pct=official_return,
                official_max_dd_pct=official_dd,
                official_sharpe=official_sharpe,
                official_broker10_peak_pct=official_broker,
                source_path=spec.path,
            )
        )
    return records


def _records_from_metrics(spec: MetricsSpec) -> list[dict[str, Any]]:
    frame = _read_csv(spec.path)
    official = _find_official_row(frame, spec.official_variant_values)
    official_return = _safe_float(official.get("total_return_pct"))
    if not np.isfinite(official_return):
        official_return = _safe_float(official.get("total_return_pct", official.get("total_return_pct_reference")))
    official_dd = _safe_float(official.get("max_dd_pct", official.get("total_wealth_max_dd_pct")))
    official_sharpe = _safe_float(official.get("sharpe"))
    official_broker = _safe_float(
        official.get("max_broker10_margin_to_equity_pct", official.get("max_broker10_to_total_wealth_pct"))
    )
    records = []
    for _, row in frame.iterrows():
        if _is_official_row(row, official, spec.variant_col):
            continue
        label = str(row.get(spec.variant_col, row.get("variant", row.get("arm", spec.stage))))
        total_return = _safe_float(row.get("total_return_pct"))
        return_retention = _safe_float(row.get("return_retention_pct"))
        if not np.isfinite(return_retention) and official_return:
            return_retention = total_return / official_return * 100.0
        max_dd = _safe_float(row.get("max_dd_pct", row.get("total_wealth_max_dd_pct")))
        dd_improvement = _safe_float(row.get("dd_improvement_pp", row.get("total_dd_improvement_pp")))
        if not np.isfinite(dd_improvement):
            dd_improvement = max_dd - official_dd
        broker = _safe_float(
            row.get("max_broker10_margin_to_equity_pct", row.get("max_broker10_to_total_wealth_pct"))
        )
        end_equity = _safe_float(row.get("end_equity", row.get("end_total_equity")))
        records.append(
            _base_record(
                stage=spec.stage,
                label=label,
                route_family=spec.route_family,
                evidence_type=spec.evidence_type,
                verdict=spec.verdict,
                route_note=spec.route_note,
                end_equity=end_equity,
                total_return_pct=total_return,
                return_retention_pct=return_retention,
                max_dd_pct=max_dd,
                dd_improvement_pp=dd_improvement,
                sharpe=_safe_float(row.get("sharpe")),
                broker10_peak_pct=broker,
                official_return_pct=official_return,
                official_max_dd_pct=official_dd,
                official_sharpe=official_sharpe,
                official_broker10_peak_pct=official_broker,
                source_path=spec.path,
            )
        )
    return records


def _records_from_upper_bound(spec: UpperBoundSpec) -> list[dict[str, Any]]:
    frame = _read_csv(spec.path)
    row = frame.iloc[0]
    official_return = _safe_float(row[OFFICIAL_RETURN_COL])
    official_dd = _safe_float(row[OFFICIAL_DD_COL])
    official_sharpe = _safe_float(row.get("official_sharpe"))
    official_broker = _safe_float(row.get(OFFICIAL_BROKER_COL))
    total_return = _safe_float(row.get("upper_bound_total_return_pct"))
    max_dd = _safe_float(row.get("upper_bound_max_dd_pct"))
    dd_improvement = _safe_float(row.get("upper_bound_max_dd_improvement_pp"))
    if not np.isfinite(dd_improvement):
        dd_improvement = max_dd - official_dd
    return [
        _base_record(
            stage=spec.stage,
            label=spec.candidate_label,
            route_family=spec.route_family,
            evidence_type=spec.evidence_type,
            verdict=spec.verdict,
            route_note=spec.route_note,
            end_equity=_safe_float(row.get("upper_bound_end_equity")),
            total_return_pct=total_return,
            return_retention_pct=_safe_float(row.get("upper_bound_return_retention_pct")),
            max_dd_pct=max_dd,
            dd_improvement_pp=dd_improvement,
            sharpe=_safe_float(row.get("upper_bound_sharpe")),
            broker10_peak_pct=official_broker,
            official_return_pct=official_return,
            official_max_dd_pct=official_dd,
            official_sharpe=official_sharpe,
            official_broker10_peak_pct=official_broker,
            source_path=spec.path,
        )
    ]


def _build_frontier() -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for spec in TWO_ARM_SPECS:
        records.extend(_records_from_two_arm(spec))
    for spec in METRICS_SPECS:
        records.extend(_records_from_metrics(spec))
    for spec in UPPER_BOUND_SPECS:
        records.extend(_records_from_upper_bound(spec))
    frame = pd.DataFrame(records)
    frame["return_shortfall_to_80"] = (TARGET_RETURN_RETENTION - frame["return_retention_pct"]).clip(lower=0)
    frame["dd_shortfall_to_5pp"] = (TARGET_DD_IMPROVEMENT - frame["dd_improvement_pp"]).clip(lower=0)
    frame["broker10_worse_pp"] = (
        frame["broker10_peak_pct"] - frame["official_broker10_peak_pct"]
    ).clip(lower=0)
    frame["rough_frontier_distance"] = (
        frame["return_shortfall_to_80"]
        + 4.0 * frame["dd_shortfall_to_5pp"]
        + 0.25 * frame["broker10_worse_pp"]
        + np.where(frame["evidence_type"].eq("true_engine"), 0.0, 10.0)
    )
    return frame.sort_values(["strict_candidate_pass", "rough_frontier_distance"], ascending=[False, True])


def _route_summary(frontier: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for family, group in frontier.groupby("route_family", sort=True):
        best_dd = group.loc[group["dd_improvement_pp"].idxmax()]
        best_retention = group.loc[group["return_retention_pct"].idxmax()]
        nearest = group.loc[group["rough_frontier_distance"].idxmin()]
        rows.append(
            {
                "route_family": family,
                "tested_variant_count": len(group),
                "evidence_types": ",".join(sorted(group["evidence_type"].unique())),
                "strict_candidate_pass_count": int(group["strict_candidate_pass"].sum()),
                "best_dd_stage": best_dd["stage"],
                "best_dd_label": best_dd["label"],
                "best_dd_improvement_pp": best_dd["dd_improvement_pp"],
                "best_dd_return_retention_pct": best_dd["return_retention_pct"],
                "best_retention_stage": best_retention["stage"],
                "best_retention_label": best_retention["label"],
                "best_retention_pct": best_retention["return_retention_pct"],
                "nearest_stage": nearest["stage"],
                "nearest_label": nearest["label"],
                "nearest_failure_reasons": nearest["failure_reasons"],
                "route_verdict": "; ".join(sorted(group["verdict"].unique())),
            }
        )
    return pd.DataFrame(rows).sort_values("route_family")


def _plot_frontier(frontier: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 8.5))
    x_max = max(110.0, frontier["return_retention_pct"].max() + 3)
    y_max = max(12.0, frontier["dd_improvement_pp"].max() + 2)
    ax.add_patch(
        Rectangle(
            (TARGET_RETURN_RETENTION, TARGET_DD_IMPROVEMENT),
            x_max - TARGET_RETURN_RETENTION,
            y_max - TARGET_DD_IMPROVEMENT,
            facecolor="#dcfce7",
            edgecolor="none",
            alpha=0.45,
            zorder=0,
            label="metric target region",
        )
    )
    ax.axvline(TARGET_RETURN_RETENTION, color="black", linestyle="--", linewidth=1.0)
    ax.axhline(TARGET_DD_IMPROVEMENT, color="black", linestyle="--", linewidth=1.0)
    color_map = {"true_engine": "#2563eb", "proxy": "#f97316", "upper_bound": "#7c3aed"}
    marker_map = {"true_engine": "o", "proxy": "s", "upper_bound": "^"}
    for evidence, group in frontier.groupby("evidence_type"):
        ax.scatter(
            group["return_retention_pct"],
            group["dd_improvement_pp"],
            s=90,
            marker=marker_map.get(evidence, "o"),
            c=color_map.get(evidence, "#374151"),
            alpha=0.85,
            edgecolor="white",
            linewidth=0.8,
            label=evidence,
        )
    labels_to_annotate = {
        "Stage009",
        "Stage018",
        "Stage020",
        "Stage048",
        "Stage049",
        "Stage002",
        "Stage046",
    }
    for _, row in frontier.iterrows():
        if row["stage"] in labels_to_annotate:
            ax.annotate(
                f"{row['stage']}\n{row['label'][:22]}",
                (row["return_retention_pct"], row["dd_improvement_pp"]),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=8,
                alpha=0.9,
            )
    ax.set_title("Stage050 route frontier: no tested route reaches deployable target region")
    ax.set_xlabel("Return retention vs official (%)")
    ax.set_ylabel("Max drawdown improvement vs official (pp)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _load_curve(spec: CurveSpec) -> pd.DataFrame:
    frame = _read_csv(spec.path)
    if spec.filter_col and spec.filter_value:
        frame = frame[frame[spec.filter_col].astype(str).eq(spec.filter_value)].copy()
    if frame.empty:
        raise RuntimeError(f"empty curve after filter for {spec.label}")
    out = frame[["date", spec.equity_col, spec.drawdown_col]].copy()
    out.columns = ["date", "equity", "drawdown_pct"]
    out["date"] = pd.to_datetime(out["date"])
    out["label"] = spec.label
    out["evidence_type"] = spec.evidence_type
    return out.sort_values("date")


def _plot_paths() -> None:
    curves = [_load_curve(spec) for spec in CURVE_SPECS]
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.3, 1.1]})
    official = curves[0][["date", "equity"]].rename(columns={"equity": "official_equity"})
    for curve, spec in zip(curves, CURVE_SPECS):
        axes[0].plot(curve["date"], curve["equity"], spec.line_style, linewidth=1.5, label=spec.label)
        axes[1].plot(curve["date"], curve["drawdown_pct"], spec.line_style, linewidth=1.3, label=spec.label)
        merged = curve.merge(official, on="date", how="left")
        merged["equity_gap"] = merged["equity"] - merged["official_equity"]
        if spec.evidence_type != "official":
            axes[2].plot(merged["date"], merged["equity_gap"], spec.line_style, linewidth=1.3, label=spec.label)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("equity gap vs official")
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    axes[0].set_title("Stage050 representative paths: apparent drawdown repair often cuts the right-tail base")
    fig.tight_layout()
    fig.savefig(PATH_OUT, dpi=160)
    plt.close(fig)


def _plot_failure_reasons(frontier: pd.DataFrame) -> None:
    exploded = frontier.assign(reason=frontier["failure_reasons"].str.split(";")).explode("reason")
    counts = exploded[exploded["reason"].ne("none")]["reason"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(11, 6))
    counts.plot(kind="barh", ax=ax, color="#64748b")
    ax.set_title("Stage050 failure reasons across tested routes")
    ax.set_xlabel("count")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FAILURE_OUT, dpi=160)
    plt.close(fig)


def _fmt(value: Any, digits: int = 4) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not np.isfinite(value):
        return "NA"
    return f"{value:.{digits}f}"


def _md_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    display = frame[columns].head(max_rows).copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda v: _fmt(v, 4))
    lines = [
        "| " + " | ".join(display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in display.columns) + " |")
    return "\n".join(lines)


def _write_report(frontier: pd.DataFrame, route_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    nearest = frontier.iloc[0]
    true_engine = frontier[frontier["evidence_type"].eq("true_engine")]
    best_true_dd = true_engine.loc[true_engine["dd_improvement_pp"].idxmax()]
    report = f"""# Stage050 route frontier overfit audit

## Positioning

- Official version: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`.
- This is a meta-audit of existing line evidence. It is not a new trading rule, not a true engine, not an A/B candidate, and not a live rule.
- No official config, CTP path, order API, product whitelist, year filter, or threshold is changed.
- Target region is frozen from the line objective: return retention >= `{TARGET_RETURN_RETENTION:.0f}%`, max drawdown improvement >= `{TARGET_DD_IMPROVEMENT:.0f}pp`, broker10 not worse, Sharpe not materially lower, and deployable evidence must be a true engine.

## Headline

- Tested records collected: `{len(frontier)}`.
- Strict deployable candidate pass count: `{int(frontier['strict_candidate_pass'].sum())}`.
- Best true-engine drawdown repair: `{best_true_dd['stage']}` / `{best_true_dd['label']}` with DD improvement `{_fmt(best_true_dd['dd_improvement_pp'])}pp`, but return retention `{_fmt(best_true_dd['return_retention_pct'])}%`.
- Nearest record by rough frontier distance: `{nearest['stage']}` / `{nearest['label']}`; failure reasons `{nearest['failure_reasons']}`.
- Decision: `{decision['decision']}`.

## Frontier Table

{_md_table(frontier, ['stage', 'label', 'evidence_type', 'route_family', 'return_retention_pct', 'dd_improvement_pp', 'broker10_peak_pct', 'strict_candidate_pass', 'failure_reasons'], 30)}

## Route Family Summary

{_md_table(route_summary, ['route_family', 'tested_variant_count', 'evidence_types', 'strict_candidate_pass_count', 'best_dd_stage', 'best_dd_improvement_pp', 'best_dd_return_retention_pct', 'nearest_stage', 'nearest_failure_reasons'], 30)}

## Visual Outputs

- Return/drawdown frontier: `{SCATTER_OUT}`
- Representative path chart: `{PATH_OUT}`
- Failure reason chart: `{FAILURE_OUT}`

## Judgment

The line has not failed because one threshold was slightly wrong. The visual frontier shows a structural tradeoff: true minute exits or risk cuts can reduce drawdown only by cutting the right-tail base, while proxy and upper-bound ideas either fail true-engine conversion, have tiny drawdown repair, worsen broker10, or lack data coverage. Continuing by slicing products, years, directions, windows, R thresholds, or nearby cutoffs would be multiple-testing overfit.

The next useful work must therefore be one of two non-overfit paths:

1. Data engineering first: complete and point-in-time validate external data coverage before retesting a fixed external source such as product trend t-stat or member ranks.
2. New predeclared minute replay candidate on the Stage045 synchronized timestamp-ready subset, using information available before or at execution time and keeping fallback/no-proxy samples on the official path.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frontier = _build_frontier()
    route_summary = _route_summary(frontier)
    _plot_frontier(frontier)
    _plot_paths()
    _plot_failure_reasons(frontier)

    strict_count = int(frontier["strict_candidate_pass"].sum())
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage050_no_existing_route_candidate_continue_only_new_predeclared_or_data_engineering",
        "strict_candidate_pass_count": strict_count,
        "tested_record_count": int(len(frontier)),
        "target_return_retention_pct": TARGET_RETURN_RETENTION,
        "target_dd_improvement_pp": TARGET_DD_IMPROVEMENT,
        "next_allowed_routes": [
            "complete_point_in_time_external_data_coverage_then_rerun_fixed_spec",
            "new_predeclared_stage045_timestamp_ready_minute_replay_candidate_with_fallback_official_path",
        ],
        "blocked_routes": sorted(frontier["route_family"].unique().tolist()),
        "outputs": {
            "frontier_metrics": FRONTIER_OUT,
            "route_family_summary": ROUTE_SUMMARY_OUT,
            "report": REPORT_OUT,
            "frontier_chart": SCATTER_OUT,
            "representative_path_chart": PATH_OUT,
            "failure_reason_chart": FAILURE_OUT,
        },
    }
    frontier.to_csv(FRONTIER_OUT, index=False, encoding="utf-8-sig")
    route_summary.to_csv(ROUTE_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    NEXT_ROUTE_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(frontier, route_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
