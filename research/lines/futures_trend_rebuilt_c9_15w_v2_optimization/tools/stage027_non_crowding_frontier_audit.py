from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage027"
MODEL_TAG = "stage027_non_crowding_frontier_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage027_non_crowding_frontier_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage027_non_crowding_frontier_audit"
STAGES_DIR = LINE_DIR / "stages"

FRONTIER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_table_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0718_stage027_non_crowding_frontier_audit.md"

BASELINE_NEGATIVE_COUNT = 330_947
BASELINE_MIN_RETURN_PCT = -43.793975945374505
BASELINE_TO_FINAL_NEGATIVE_COUNT = 0
BASELINE_TO_FINAL_MIN_RETURN_PCT = 26.675296135498748


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _base_frontier_row(
    *,
    stage: str,
    variant: str,
    structure_family: str,
    evidence_tier: str,
    decision: str,
    note: str,
    source_path: Path | str = "",
    parameter_rescue_allowed: int = 0,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "variant": variant,
        "structure_family": structure_family,
        "evidence_tier": evidence_tier,
        "decision": decision,
        "note": note,
        "source_path": str(source_path),
        "all_gt1y_window_count": np.nan,
        "all_gt1y_negative_count": np.nan,
        "all_gt1y_min_return_pct": np.nan,
        "to_final_window_count": np.nan,
        "to_final_negative_count": np.nan,
        "to_final_min_return_pct": np.nan,
        "retention_80pct_pass_count": np.nan,
        "retention_rows": np.nan,
        "min_retention": np.nan,
        "median_total_return_pct": np.nan,
        "min_total_return_pct": np.nan,
        "worst_max_drawdown_pct": np.nan,
        "median_sharpe": np.nan,
        "objective_pass": 0,
        "realized_or_future_pnl": np.nan,
        "sample_count": np.nan,
        "year_count": np.nan,
        "oos_positive_fold_count": np.nan,
        "oos_test_fold_count": np.nan,
        "worst_year_pnl": np.nan,
        "parameter_rescue_allowed": int(parameter_rescue_allowed),
    }


def summarize_variant_goal_table(
    goal_table: pd.DataFrame,
    *,
    variant: str,
    stage: str,
    structure_family: str,
    evidence_tier: str,
    decision: str,
    note: str,
    source_path: Path | str = "",
    parameter_rescue_allowed: int = 0,
) -> dict[str, Any]:
    matches = goal_table[goal_table["variant"].astype(str).eq(variant)].copy()
    if matches.empty:
        raise ValueError(f"variant not found in goal table: {variant}")
    item = matches.iloc[0]
    row = _base_frontier_row(
        stage=stage,
        variant=variant,
        structure_family=structure_family,
        evidence_tier=evidence_tier,
        decision=decision,
        note=note,
        source_path=source_path,
        parameter_rescue_allowed=parameter_rescue_allowed,
    )
    for key in (
        "all_gt1y_window_count",
        "all_gt1y_negative_count",
        "all_gt1y_min_return_pct",
        "to_final_window_count",
        "to_final_negative_count",
        "to_final_min_return_pct",
        "retention_80pct_pass_count",
        "retention_rows",
        "min_retention",
        "median_total_return_pct",
        "min_total_return_pct",
        "worst_max_drawdown_pct",
        "median_sharpe",
        "objective_pass",
    ):
        if key in item.index:
            row[key] = item[key]
    if "retention_vs_stage013_pass_count" in item.index:
        row["retention_80pct_pass_count"] = item["retention_vs_stage013_pass_count"]
    elif "retention_vs_base_stage006_pass_count" in item.index:
        row["retention_80pct_pass_count"] = item["retention_vs_base_stage006_pass_count"]
    return row


def summarize_goal_aggregate(
    goal_aggregate: pd.DataFrame,
    *,
    variant: str,
    stage: str,
    structure_family: str,
    evidence_tier: str,
    decision: str,
    note: str,
    source_path: Path | str = "",
    retention: pd.DataFrame | None = None,
    parameter_rescue_allowed: int = 0,
) -> dict[str, Any]:
    matches = goal_aggregate[goal_aggregate["variant"].astype(str).eq(variant)].copy()
    if matches.empty:
        raise ValueError(f"variant not found in goal aggregate: {variant}")
    row = _base_frontier_row(
        stage=stage,
        variant=variant,
        structure_family=structure_family,
        evidence_tier=evidence_tier,
        decision=decision,
        note=note,
        source_path=source_path,
        parameter_rescue_allowed=parameter_rescue_allowed,
    )
    all_gt1y = matches[matches["audit_scope"].astype(str).eq("all_trading_end_dates_gt_1y")]
    to_final = matches[matches["audit_scope"].astype(str).eq("start_to_2026_06_30_only")]
    if not all_gt1y.empty:
        row["all_gt1y_window_count"] = int(pd.to_numeric(all_gt1y["window_count"], errors="coerce").sum())
        row["all_gt1y_negative_count"] = int(pd.to_numeric(all_gt1y["negative_count"], errors="coerce").sum())
        row["all_gt1y_min_return_pct"] = float(pd.to_numeric(all_gt1y["min_return_pct"], errors="coerce").min())
    if not to_final.empty:
        row["to_final_window_count"] = int(pd.to_numeric(to_final["window_count"], errors="coerce").sum())
        row["to_final_negative_count"] = int(pd.to_numeric(to_final["negative_count"], errors="coerce").sum())
        row["to_final_min_return_pct"] = float(pd.to_numeric(to_final["min_return_pct"], errors="coerce").min())

    if retention is not None and not retention.empty:
        candidate_cols = [col for col in retention.columns if "passes_80pct" in col]
        ratio_cols = [col for col in retention.columns if col.endswith("_return_ratio")]
        if "variant" in retention.columns:
            retention = retention[retention["variant"].astype(str).eq(variant)]
        if not retention.empty and candidate_cols:
            pass_col = candidate_cols[-1]
            row["retention_80pct_pass_count"] = int(pd.to_numeric(retention[pass_col], errors="coerce").fillna(0).sum())
            row["retention_rows"] = int(len(retention))
        if not retention.empty and ratio_cols:
            ratio_col = ratio_cols[-1]
            row["min_retention"] = float(pd.to_numeric(retention[ratio_col], errors="coerce").min())
    return row


def summarize_decision_metrics(
    decision_data: dict[str, Any],
    *,
    stage: str,
    variant: str,
    structure_family: str,
    evidence_tier: str,
    decision: str,
    note: str,
    source_path: Path | str = "",
    metric_prefix: str = "",
    parameter_rescue_allowed: int = 0,
) -> dict[str, Any]:
    row = _base_frontier_row(
        stage=stage,
        variant=variant,
        structure_family=structure_family,
        evidence_tier=evidence_tier,
        decision=decision,
        note=note,
        source_path=source_path,
        parameter_rescue_allowed=parameter_rescue_allowed,
    )
    prefix = f"{metric_prefix}_" if metric_prefix else ""
    mapping = {
        "all_gt1y_window_count": f"{prefix}all_gt1y_window_count",
        "all_gt1y_negative_count": f"{prefix}all_gt1y_negative_count",
        "all_gt1y_min_return_pct": f"{prefix}all_gt1y_min_return_pct",
        "to_final_negative_count": f"{prefix}to_final_negative_count",
        "to_final_min_return_pct": f"{prefix}to_final_min_return_pct",
        "retention_80pct_pass_count": "retention_vs_stage013_pass_count",
        "retention_rows": "retention_rows",
        "median_total_return_pct": "candidate_median_return_pct",
        "min_total_return_pct": "candidate_min_return_pct",
        "worst_max_drawdown_pct": "candidate_worst_max_dd_pct",
        "median_sharpe": "candidate_median_sharpe",
    }
    for out_key, in_key in mapping.items():
        if in_key in decision_data:
            row[out_key] = decision_data[in_key]
    return row


def summarize_signal_table(
    data: pd.DataFrame,
    *,
    key_column: str,
    key_value: str,
    stage: str,
    structure_family: str,
    evidence_tier: str,
    decision: str,
    note: str,
    source_path: Path | str = "",
    parameter_rescue_allowed: int = 0,
) -> dict[str, Any]:
    matches = data[data[key_column].astype(str).eq(key_value)].copy()
    if matches.empty:
        raise ValueError(f"signal row not found: {key_value}")
    item = matches.iloc[0]
    row = _base_frontier_row(
        stage=stage,
        variant=key_value,
        structure_family=structure_family,
        evidence_tier=evidence_tier,
        decision=decision,
        note=note,
        source_path=source_path,
        parameter_rescue_allowed=parameter_rescue_allowed,
    )
    row["realized_or_future_pnl"] = item.get("total_future_net_pnl_60d", item.get("total_pnl", np.nan))
    row["sample_count"] = item.get("count", np.nan)
    row["year_count"] = item.get("year_count", np.nan)
    row["oos_positive_fold_count"] = item.get("oos_positive_fold_count", np.nan)
    row["oos_test_fold_count"] = item.get("oos_fold_count", item.get("oos_test_fold_count", np.nan))
    row["worst_year_pnl"] = item.get("min_year_pnl", item.get("worst_year_pnl", np.nan))
    row["objective_pass"] = int(bool(item.get("stage077_independent_candidate", item.get("member_rank_signal_candidate", False))))
    return row


def classify_frontier_row(
    row: dict[str, Any] | pd.Series,
    *,
    baseline_negative_count: int,
    baseline_min_return_pct: float = BASELINE_MIN_RETURN_PCT,
) -> dict[str, Any]:
    data = dict(row)
    reasons: list[str] = []
    all_negative = _as_float(data.get("all_gt1y_negative_count"))
    min_return = _as_float(data.get("all_gt1y_min_return_pct"))
    to_final_negative = _as_float(data.get("to_final_negative_count"))
    min_retention = _as_float(data.get("min_retention"))
    retention_pass_count = _as_float(data.get("retention_80pct_pass_count"))
    retention_rows = _as_float(data.get("retention_rows"))
    objective_pass = _as_int(data.get("objective_pass"))
    parameter_rescue_allowed = bool(_as_int(data.get("parameter_rescue_allowed")))

    if not np.isnan(all_negative):
        if all_negative > baseline_negative_count:
            reasons.append("left_tail_worse")
        elif all_negative > 0:
            reasons.append("strict_gt1y_negative_remaining")
    else:
        reasons.append("no_dense_goal_curve")
    if not np.isnan(min_return) and min_return < baseline_min_return_pct:
        reasons.append("worst_return_worse")
    if not np.isnan(to_final_negative) and to_final_negative > 0:
        reasons.append("to_final_negative")
    if not np.isnan(min_retention) and min_retention < 0.8:
        reasons.append("retention_fail")
    if not np.isnan(retention_rows) and retention_rows > 0 and not np.isnan(retention_pass_count):
        if retention_pass_count < retention_rows:
            reasons.append("retention_fail")
    reasons = list(dict.fromkeys(reasons))
    if objective_pass != 1:
        reasons.append("objective_not_met")
    if not parameter_rescue_allowed:
        reasons.append("no_parameter_rescue")

    if objective_pass == 1 and not reasons:
        status = "promotion_candidate"
    elif (
        not np.isnan(all_negative)
        and all_negative < baseline_negative_count
        and (np.isnan(min_return) or min_return >= baseline_min_return_pct)
        and (np.isnan(to_final_negative) or to_final_negative == 0)
        and (np.isnan(min_retention) or min_retention >= 0.8)
        and (
            np.isnan(retention_rows)
            or retention_rows <= 0
            or np.isnan(retention_pass_count)
            or retention_pass_count >= retention_rows
        )
    ):
        status = "frontier_signal"
    elif not np.isnan(all_negative) and all_negative < baseline_negative_count:
        status = "diagnostic_only"
    else:
        status = "reject"

    data["frontier_status"] = status
    data["failure_reasons"] = ",".join(reasons)
    data["negative_delta_vs_stage013"] = all_negative - baseline_negative_count if not np.isnan(all_negative) else np.nan
    return data


def make_frontier_decision(
    frontier: pd.DataFrame,
    *,
    baseline_negative_count: int,
    baseline_min_return_pct: float = BASELINE_MIN_RETURN_PCT,
) -> dict[str, Any]:
    classified = pd.DataFrame(
        [
            classify_frontier_row(
                row,
                baseline_negative_count=baseline_negative_count,
                baseline_min_return_pct=baseline_min_return_pct,
            )
            for row in frontier.to_dict("records")
        ]
    )
    promoted = classified[classified["frontier_status"].eq("promotion_candidate")]
    frontiers = classified[classified["frontier_status"].eq("frontier_signal")]

    if not promoted.empty:
        decision = "stage027_has_candidate_needs_true_ab_validation"
        best_next_direction = str(promoted.iloc[0]["structure_family"])
    elif not frontiers.empty and frontiers["structure_family"].astype(str).str.contains("xsmom_confirmation").any():
        decision = "stage027_no_candidate_promoted_use_frontier_for_next_hypothesis"
        best_next_direction = "xsmom_confirmation_true_engine_or_new_pit_source"
    elif not frontiers.empty:
        decision = "stage027_no_candidate_promoted_use_frontier_for_next_hypothesis"
        best_next_direction = str(frontiers.iloc[0]["structure_family"])
    else:
        decision = "stage027_no_candidate_promoted_need_new_external_source_or_account_structure"
        best_next_direction = "new_pit_source_or_non_crowding_account_structure"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "promoted_candidate_count": int(len(promoted)),
        "frontier_signal_count": int(len(frontiers)),
        "best_next_direction": best_next_direction,
        "baseline_negative_count": int(baseline_negative_count),
        "parameter_rescue_allowed": False,
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following references support diversification and capital overlays, while meta-labeling "
            "requires stable OOS evidence. Existing C9 evidence says parameter rescue on the same AI "
            "quality fields is lower value than structure or new PIT information."
        ),
        "overfit_reflection_before": (
            "否。本阶段只读冻结输出，不新增交易规则、不按坏窗口、品种、方向、月份调参。"
        ),
        "overfit_reflection_after": (
            "否。结论来自统一前沿表；若把失败候选继续改成相邻阈值、权重、rank 或 rounding，就是过拟合。"
        ),
        "continue_value_before": (
            "有。Stage026 后需要决定下一步研究战场，否则容易继续在同一批字段上救参。"
        ),
        "continue_value_after": (
            "有，但只应沿前沿信号进入真实引擎或新 PIT 源；当前没有任何候选可直接接实盘。"
        ),
    }


def _load_frontier_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    stage013_dir = LINE_DIR / "outputs" / "stage013_guarded_quality_add_risk_proxy"
    stage013_goal = stage013_dir / "rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_goal_aggregate_stage013_guarded_quality_add_risk_proxy_v1.csv"
    stage013_ret = stage013_dir / "rebuilt_c9_v2_stage013_guarded_quality_add_risk_proxy_retention_vs_stage013_stage013_guarded_quality_add_risk_proxy_v1.csv"
    rows.append(
        summarize_goal_aggregate(
            _read_csv(stage013_goal),
            variant="stage013_guarded_quality_add_risk_proxy",
            stage="Stage013",
            structure_family="ai_quality_add_risk",
            evidence_tier="closed_lot_proxy",
            decision="stage013_guarded_proxy_improves_stage010_left_tail_need_true_engine",
            note="质量加风险 proxy 有价值但 Stage026 真引擎已反证简单落地。",
            source_path=stage013_goal,
            retention=_read_csv(stage013_ret),
        )
    )

    stage017_decision = LINE_DIR / "outputs" / "stage017_fixed_sleeve_blend_audit" / (
        "rebuilt_c9_v2_stage017_fixed_sleeve_blend_audit_decision_stage017_fixed_sleeve_blend_audit_v1.json"
    )
    d017 = _read_json(stage017_decision)
    rows.append(
        {
            **_base_frontier_row(
                stage="Stage017",
                variant="best_non_c9_fixed_sleeve_blend",
                structure_family="fixed_official_c9_blend",
                evidence_tier="curve_proxy",
                decision=str(d017.get("decision", "")),
                note="固定 C9/Stage372 资金袖组合不达标，不能继续扫 65/75/85 权重。",
                source_path=stage017_decision,
            ),
            "all_gt1y_negative_count": d017.get("best_non_c9_all_gt1y_negative_count", np.nan),
            "all_gt1y_min_return_pct": d017.get("best_non_c9_all_gt1y_min_return_pct", np.nan),
            "min_retention": d017.get("best_non_c9_min_retention", np.nan),
            "objective_pass": d017.get("objective_pass_variant_count", 0),
        }
    )

    stage021_dir = LINE_DIR / "outputs" / "stage021_xsmom_non_crowding_overlay_proxy"
    stage021_goal = stage021_dir / "rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_variant_goal_table_stage021_xsmom_non_crowding_overlay_proxy_v1.csv"
    d021 = _read_json(
        stage021_dir / "rebuilt_c9_v2_stage021_xsmom_non_crowding_overlay_proxy_decision_stage021_xsmom_non_crowding_overlay_proxy_v1.json"
    )
    rows.append(
        summarize_variant_goal_table(
            _read_csv(stage021_goal),
            variant=str(d021.get("best_variant")),
            stage="Stage021",
            structure_family="independent_sleeve",
            evidence_tier="curve_proxy",
            decision=str(d021.get("decision", "")),
            note="固定 xsmom 非挤占 overlay 左尾略坏，不应继续扫权重/成本/lookback。",
            source_path=stage021_goal,
        )
    )

    stage022_dir = LINE_DIR / "outputs" / "stage022_xsmom_entry_confirmation_proxy"
    stage022_goal = stage022_dir / "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_variant_goal_table_stage022_xsmom_entry_confirmation_proxy_v1.csv"
    d022 = _read_json(
        stage022_dir / "rebuilt_c9_v2_stage022_xsmom_entry_confirmation_proxy_decision_stage022_xsmom_entry_confirmation_proxy_v1.json"
    )
    rows.append(
        summarize_variant_goal_table(
            _read_csv(stage022_goal),
            variant=str(d022.get("best_variant")),
            stage="Stage022",
            structure_family="xsmom_confirmation",
            evidence_tier="closed_lot_curve_proxy",
            decision=str(d022.get("decision", "")),
            note="xsmom 作为入场确认有前沿价值，但仍是 proxy，需真引擎或换新 PIT 源。",
            source_path=stage022_goal,
        )
    )

    stage026_dir = LINE_DIR / "outputs" / "stage026_cool_quality_add_risk_engine"
    stage026_goal = stage026_dir / "rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_goal_aggregate_stage026_cool_quality_add_risk_engine_v1.csv"
    stage026_ret = stage026_dir / "rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_retention_vs_stage013_stage026_cool_quality_add_risk_engine_v1.csv"
    d026 = _read_json(
        stage026_dir / "rebuilt_c9_v2_stage026_cool_quality_add_risk_engine_decision_stage026_cool_quality_add_risk_engine_v1.json"
    )
    rows.append(
        summarize_goal_aggregate(
            _read_csv(stage026_goal),
            variant="stage026_engine",
            stage="Stage026",
            structure_family="ai_quality_add_risk",
            evidence_tier="true_engine",
            decision=str(d026.get("decision", "")),
            note="冷静高质量 floor25 真引擎恶化左尾和到终点负窗口，停止 rounding/rank/RSI 救参。",
            source_path=stage026_goal,
            retention=_read_csv(stage026_ret),
        )
    )

    stage074_dir = UPSTREAM_LINE_DIR / "outputs" / "stage074_cold_start_capital_ramp_proxy"
    stage074_goal = stage074_dir / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_goal_aggregate_stage074_cold_start_capital_ramp_proxy_v1.csv"
    stage074_ret = stage074_dir / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_retention_stage074_cold_start_capital_ramp_proxy_v1.csv"
    d074 = _read_json(stage074_dir / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_decision_stage074_cold_start_capital_ramp_proxy_v1.json")
    rows.append(
        summarize_goal_aggregate(
            _read_csv(stage074_goal),
            variant="full_market_ai_top8_and_active_positions_lt3_cold_start_ramp",
            stage="Stage074",
            structure_family="cold_start_account_outer_layer",
            evidence_tier="account_proxy",
            decision=str(d074.get("decision", "")),
            note="线性冷启动 ramp 改善部分最差区间但牺牲恢复段，不继续调 floor/ramp_days。",
            source_path=stage074_goal,
            retention=_read_csv(stage074_ret),
        )
    )

    stage075_dir = UPSTREAM_LINE_DIR / "outputs" / "stage075_staggered_sleeve_deployment_proxy"
    stage075_goal = stage075_dir / "rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_variant_summary_stage075_staggered_sleeve_deployment_proxy_v1.csv"
    d075 = _read_json(stage075_dir / "rebuilt_c9_stage075_staggered_sleeve_deployment_proxy_decision_stage075_staggered_sleeve_deployment_proxy_v1.json")
    rows.append(
        summarize_variant_goal_table(
            _read_csv(stage075_goal),
            variant="full_market_ai_top8_and_active_positions_lt3_staggered_sleeve",
            stage="Stage075",
            structure_family="staggered_account_outer_layer",
            evidence_tier="account_proxy",
            decision=str(d075.get("decision", "")),
            note="固定四袖分批部署不达标，不继续扫 sleeve_count/offset。",
            source_path=stage075_goal,
        )
    )

    stage077_dir = UPSTREAM_LINE_DIR / "outputs" / "stage077_jd_independent_candidate_audit"
    stage077_cond = stage077_dir / "rebuilt_c9_stage077_jd_independent_candidate_audit_condition_summary_stage077_jd_independent_candidate_audit_v1.csv"
    d077 = _read_json(stage077_dir / "rebuilt_c9_stage077_jd_independent_candidate_audit_decision_stage077_jd_independent_candidate_audit_v1.json")
    rows.append(
        summarize_signal_table(
            _read_csv(stage077_cond),
            key_column="condition",
            key_value="jd_ai_top8_independent",
            stage="Stage077",
            structure_family="jd_independent_sleeve",
            evidence_tier="signal_readonly",
            decision=str(d077.get("decision", "")),
            note="鸡蛋 AI top8 独立候选样本小且 OOS fold 不稳，只能观察。",
            source_path=stage077_cond,
        )
    )

    stage081_dir = UPSTREAM_LINE_DIR / "outputs" / "stage081_member_rank_signal_audit"
    stage081_summary = stage081_dir / "rebuilt_c9_stage081_member_rank_signal_audit_summary_stage081_member_rank_signal_audit_v1.csv"
    d081 = _read_json(stage081_dir / "rebuilt_c9_stage081_member_rank_signal_audit_decision_stage081_member_rank_signal_audit_v1.json")
    rows.append(
        summarize_signal_table(
            _read_csv(stage081_summary),
            key_column="condition",
            key_value="account_injured_and_member_position_flow_aligned",
            stage="Stage081",
            structure_family="member_rank_external_pit",
            evidence_tier="signal_readonly",
            decision=str(d081.get("decision", "")),
            note="会员排名组合有方向感但最差年份硬伤，不能交易化。",
            source_path=stage081_summary,
        )
    )

    return rows


def build_frontier_table() -> pd.DataFrame:
    rows = _load_frontier_rows()
    classified = [
        classify_frontier_row(
            row,
            baseline_negative_count=BASELINE_NEGATIVE_COUNT,
            baseline_min_return_pct=BASELINE_MIN_RETURN_PCT,
        )
        for row in rows
    ]
    frame = pd.DataFrame(classified)
    sort_cols = ["frontier_status", "all_gt1y_negative_count", "stage"]
    return frame.sort_values(sort_cols, na_position="last").reset_index(drop=True)


def summarize_family(frontier: pd.DataFrame) -> pd.DataFrame:
    data = frontier.copy()
    data["has_dense_goal_curve"] = data["all_gt1y_negative_count"].notna().astype(int)
    grouped = (
        data.groupby("structure_family", dropna=False)
        .agg(
            candidate_count=("variant", "count"),
            dense_goal_count=("has_dense_goal_curve", "sum"),
            frontier_signal_count=("frontier_status", lambda s: int((s == "frontier_signal").sum())),
            reject_count=("frontier_status", lambda s: int((s == "reject").sum())),
            best_negative_count=("all_gt1y_negative_count", "min"),
            best_min_return_pct=("all_gt1y_min_return_pct", "max"),
            best_min_retention=("min_retention", "max"),
        )
        .reset_index()
    )
    return grouped.sort_values(["frontier_signal_count", "best_negative_count"], ascending=[False, True], na_position="last")


def write_outputs() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    frontier = build_frontier_table()
    family = summarize_family(frontier)
    decision = make_frontier_decision(frontier, baseline_negative_count=BASELINE_NEGATIVE_COUNT)

    frontier.to_csv(FRONTIER_PATH, index=False, encoding="utf-8-sig")
    family.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = render_report(frontier, family, decision)
    REPORT_PATH.write_text(report, encoding="utf-8")
    STAGE_RECORD_PATH.write_text(render_stage_record(frontier, family, decision), encoding="utf-8")
    return {
        "frontier": frontier,
        "family": family,
        "decision": decision,
        "frontier_path": FRONTIER_PATH,
        "family_summary_path": FAMILY_SUMMARY_PATH,
        "decision_path": DECISION_PATH,
        "report_path": REPORT_PATH,
        "stage_record_path": STAGE_RECORD_PATH,
    }


def render_report(frontier: pd.DataFrame, family: pd.DataFrame, decision: dict[str, Any]) -> str:
    cols = [
        "stage",
        "variant",
        "structure_family",
        "evidence_tier",
        "frontier_status",
        "all_gt1y_negative_count",
        "all_gt1y_min_return_pct",
        "to_final_negative_count",
        "min_retention",
        "failure_reasons",
    ]
    return "\n".join(
        [
            "# Stage027 non-crowding frontier audit",
            "",
            "## 结论",
            "",
            f"- 决策：`{decision['decision']}`",
            f"- promoted_candidate_count：`{decision['promoted_candidate_count']}`",
            f"- frontier_signal_count：`{decision['frontier_signal_count']}`",
            f"- 下一步方向：`{decision['best_next_direction']}`",
            "- 本阶段只读：不改官方 C9/15w，不改 AI 池，不连接 CTP，不调用订单 API。",
            "",
            "## 外部调研与判断",
            "",
            "- managed futures/trend following 资料支持分散化、右尾捕获和账户层资本暴露管理。",
            "- pysystemtrade capital correction 支持账户资金暴露可动态管理，但不能用历史 drawdown 参数救线。",
            "- meta-labeling 资料支持二级信号质量层，但必须 OOS 稳定；当前 Stage015/026 已反证继续在同一批 AI 字段上救参。",
            "",
            "## 前沿表",
            "",
            _md_table(frontier[cols], max_rows=30),
            "",
            "## 结构族摘要",
            "",
            _md_table(family, max_rows=20),
            "",
            "## 反思",
            "",
            f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
            f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
            f"- 运行前继续价值反思：{decision['continue_value_before']}",
            f"- 运行后继续价值反思：{decision['continue_value_after']}",
            "",
            "## 输出",
            "",
            f"- frontier_table：`{FRONTIER_PATH}`",
            f"- family_summary：`{FAMILY_SUMMARY_PATH}`",
            f"- decision：`{DECISION_PATH}`",
            f"- report：`{REPORT_PATH}`",
            f"- stage_record：`{STAGE_RECORD_PATH}`",
            "",
        ]
    )


def render_stage_record(frontier: pd.DataFrame, family: pd.DataFrame, decision: dict[str, Any]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    compact_cols = [
        "stage",
        "variant",
        "structure_family",
        "frontier_status",
        "all_gt1y_negative_count",
        "to_final_negative_count",
        "min_retention",
    ]
    return "\n".join(
        [
            "# Stage027 非挤占结构候选前沿审计",
            "",
            f"- line_id：`{LINE_ID}`",
            "- 当前模式：`day`",
            f"- 记录时间：{now}",
            "- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`",
            "- 阶段性质：只读证据矩阵/路线选择",
            "- 是否重要突破：否",
            "- 是否触发A/B：否",
            "",
            "## 外部调研与判断",
            "",
            "- 参考资料：managed futures/trend following diversification、pysystemtrade capital correction、Hudson & Thames meta-labeling。",
            "- 我的判断：当前最应该避免在同一批 AI 质量字段、rounding、权重和冷启动参数上救参；应把下一阶段限定为结构前沿或新 PIT 信息源。",
            "",
            "## 本次变更",
            "",
            "- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage027_non_crowding_frontier_audit.py`",
            "- 修改脚本：无",
            "- 删除脚本：无",
            "- 新增参数：无交易参数；仅新增只读审计常量 `BASELINE_NEGATIVE_COUNT=330947`",
            "- 修改参数：无",
            "- 删除参数：无",
            "",
            "## 回测/归因参数",
            "",
            "- 数据区间：复用已冻结 Stage013/017/021/022/026/074/075/077/081 输出。",
            "- 账户规模：复用各阶段原口径；本阶段不重新回测。",
            "- 成本口径：复用各阶段原口径；本阶段不新增成本假设。",
            "- 样本过滤：只读各阶段已输出的候选前沿。",
            "- 策略/归因口径：统一比较严格 `>1` 年负窗口、到终点负窗口、收益保留和失败原因。",
            "",
            "## 结果",
            "",
            "- 期末权益：不适用，本阶段未回测。",
            "- 总收益：不适用，本阶段未回测。",
            "- 最大回撤：不适用，本阶段未回测。",
            "- Sharpe：不适用，本阶段未回测。",
            "- 总滑点：不适用，本阶段未回测。",
            "- 总交易次数：不适用，本阶段未回测。",
            "- 胜率：不适用，本阶段未回测。",
            f"- 其他关键指标：promoted_candidate_count `{decision['promoted_candidate_count']}`；frontier_signal_count `{decision['frontier_signal_count']}`；best_next_direction `{decision['best_next_direction']}`。",
            "",
            "## 前沿表摘要",
            "",
            _md_table(frontier[compact_cols], max_rows=30),
            "",
            "## 结构族摘要",
            "",
            _md_table(family, max_rows=20),
            "",
            "## 输出文件",
            "",
            f"- report：`{REPORT_PATH}`",
            f"- summary：`{FRONTIER_PATH}`",
            "- orders：无",
            "- daily：无",
            "- quality：无",
            "",
            "## 结论",
            "",
            f"- 本阶段结论：`{decision['decision']}`；没有任何候选可直接晋级或接实盘。",
            "- 是否进入下一步：是，但只沿 Stage022 的 xsmom 确认前沿做真引擎，或转新 PIT 信息源；不做参数救参。",
            f"- 下一步：`{decision['best_next_direction']}`。",
            "",
            "## 过拟合反思",
            "",
            f"- 运行前判断：{decision['overfit_reflection_before']}",
            f"- 运行后判断：{decision['overfit_reflection_after']}",
            "- 原因：本阶段只读冻结输出；继续救失败候选的相邻参数才是过拟合。",
            "",
            "## 继续价值反思",
            "",
            f"- 运行前判断：{decision['continue_value_before']}",
            f"- 运行后判断：{decision['continue_value_after']}",
            "- 原因：Stage026 已经反证质量加风险真引擎，下一步需要换结构或换信息源。",
            "",
            "## 合入建议",
            "",
            "- 是否更新本线 `LINE.md`：是，记录 Stage027 路线选择。",
            "- 是否更新 `research/registry.md`：是，更新二期线最新关键阶段。",
            "- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破或正式候选。",
            "",
        ]
    )


def main() -> None:
    result = write_outputs()
    decision = result["decision"]
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
