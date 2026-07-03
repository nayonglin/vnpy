from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_dense_start_goal_audit as s009
import stage039_full_market_ai_top8_proxy as s039


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage070"
MODEL_TAG = "stage070_super_quality_sibling_panel_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage070_super_quality_sibling_panel"

CANDIDATE_VARIANTS = [
    "full_market_ai_top8_and_account_injured",
    "full_market_ai_top8_and_ai_rank_1_6",
    "full_market_ai_top8_and_active_positions_lt3",
]
ADD_RISK_FRACTION = 0.25
CAPITAL = 150000.0
EPS = 1e-9

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage070_super_quality_sibling_panel"
STAGES_DIR = LINE_DIR / "stages"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE019_OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE068_OUTPUT_DIR = LINE_DIR / "outputs" / "stage068_super_quality_signal_audit"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE068_PREFIX = "rebuilt_c9_stage068_super_quality_signal_audit"
STAGE068_TAG = "stage068_super_quality_signal_audit_v1"

BASE_STAGE006_SUMMARY_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_summary_{STAGE006_TAG}.csv"
STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
STAGE013_CLOSED_LOTS_PATH = STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"
STAGE068_SUMMARY_PATH = STAGE068_OUTPUT_DIR / f"{STAGE068_PREFIX}_summary_{STAGE068_TAG}.csv"

LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv"
PANEL_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_panel_curves_{MODEL_TAG}.csv.gz"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
GOAL_AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_aggregate_{MODEL_TAG}.csv"
GOAL_WORST_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_goal_worst_windows_{MODEL_TAG}.csv"
RETENTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_retention_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s039._drawdown_pct(equity)


def _sharpe_from_equity(equity: pd.Series) -> float:
    return s039._sharpe_from_equity(equity)


def _candidate_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    index = frame.index
    full_market_ai_top8 = _to_bool(frame.get("full_market_ai_top8", False), index=index)
    account_injured = _to_bool(frame.get("account_injured", False), index=index)
    ai_rank_1_6 = _to_bool(frame.get("ai_rank_1_6", False), index=index)
    active_positions_lt3 = ~_to_bool(frame.get("active_positions_ge3", False), index=index)
    return {
        "full_market_ai_top8_and_account_injured": full_market_ai_top8 & account_injured,
        "full_market_ai_top8_and_ai_rank_1_6": full_market_ai_top8 & ai_rank_1_6,
        "full_market_ai_top8_and_active_positions_lt3": full_market_ai_top8 & active_positions_lt3,
    }


def _stage038_features(matrix: pd.DataFrame) -> pd.DataFrame:
    features = matrix.copy()
    features["requested_start_month"] = features["requested_start_month"].astype(str)
    features["open_trade_id"] = features["open_trade_id"].astype(str)
    for column in [
        "full_market_ai_top8",
        "account_injured",
        "ai_rank_1_6",
        "ai_rank_1_3",
        "active_positions_ge3",
        "selected_volume_gt1",
        "oi_confirmed",
        "account_clean",
    ]:
        if column in features.columns:
            features[column] = _to_bool(features[column], index=features.index).astype("int64")
    keep = [
        "requested_start_month",
        "open_trade_id",
        "full_market_ai_top8",
        "account_injured",
        "ai_rank_1_6",
        "ai_rank_1_3",
        "active_positions_ge3",
        "account_clean",
        "selected_volume_gt1",
        "oi_confirmed",
        "ai_rank",
        "ai_score",
        "drawdown_abs_pct",
        "loss_streak",
        "active_positions_before",
        "full_market_ai_rank_desc",
        "full_market_probability",
        "realized_pnl",
        "r_multiple_agg",
    ]
    use = [column for column in keep if column in features.columns]
    return (
        features[use]
        .sort_values(["requested_start_month", "open_trade_id"])
        .drop_duplicates(["requested_start_month", "open_trade_id"], keep="last")
        .reset_index(drop=True)
    )


def _build_panel_lot_deltas_from_frames(closed_lots: pd.DataFrame, feature_matrix: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = closed_lots.copy()
    closed["requested_start_month"] = closed["requested_start_month"].astype(str)
    closed["open_trade_id"] = closed["open_trade_id"].astype(str)
    closed["entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["realized_pnl"] = pd.to_numeric(closed["realized_pnl"], errors="coerce").fillna(0.0)

    features = _stage038_features(feature_matrix)
    masks = _candidate_masks(features)
    frames: list[pd.DataFrame] = []
    variant_audit: dict[str, Any] = {}
    for variant in CANDIDATE_VARIANTS:
        selected_features = features.loc[masks[variant]].copy()
        selected_features["stage070_feature_selected"] = 1
        merged = closed.merge(
            selected_features,
            on=["requested_start_month", "open_trade_id"],
            how="inner",
            suffixes=("", "_stage038"),
        )
        merged["candidate_variant"] = variant
        merged["stage070_add_risk_fraction"] = ADD_RISK_FRACTION
        merged["stage070_proxy_delta_pnl"] = merged["realized_pnl"] * ADD_RISK_FRACTION
        frames.append(merged)
        variant_audit[f"{variant}_selected_lots"] = int(len(merged))
        variant_audit[f"{variant}_selected_open_trades"] = (
            int(merged[["requested_start_month", "open_trade_id"]].drop_duplicates().shape[0]) if len(merged) else 0
        )
        variant_audit[f"{variant}_selected_realized_pnl"] = float(merged["realized_pnl"].sum()) if len(merged) else 0.0
        variant_audit[f"{variant}_total_proxy_delta_pnl"] = (
            float(merged["stage070_proxy_delta_pnl"].sum()) if len(merged) else 0.0
        )
    all_deltas = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    keep = [
        "candidate_variant",
        "requested_start_month",
        "lot_id",
        "open_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "volume",
        "realized_pnl",
        "r_multiple",
        "full_market_ai_top8",
        "account_injured",
        "ai_rank_1_6",
        "ai_rank_1_3",
        "active_positions_ge3",
        "account_clean",
        "selected_volume_gt1",
        "oi_confirmed",
        "ai_rank",
        "ai_score",
        "drawdown_abs_pct",
        "loss_streak",
        "active_positions_before",
        "stage070_add_risk_fraction",
        "stage070_proxy_delta_pnl",
    ]
    audit = {
        "stage013_closed_lot_count": int(len(closed)),
        "stage038_feature_key_count": int(features[["requested_start_month", "open_trade_id"]].drop_duplicates().shape[0])
        if {"requested_start_month", "open_trade_id"}.issubset(features.columns)
        else 0,
        "variant_count": len(CANDIDATE_VARIANTS),
        **variant_audit,
    }
    return all_deltas[[column for column in keep if column in all_deltas.columns]].reset_index(drop=True), audit


def _build_panel_lot_deltas() -> tuple[pd.DataFrame, dict[str, Any]]:
    closed = _read_csv(STAGE013_CLOSED_LOTS_PATH, parse_dates=["entry_date", "exit_date"])
    matrix = _read_csv(STAGE038_FEATURE_MATRIX_PATH, parse_dates=["entry_date", "exit_date"])
    return _build_panel_lot_deltas_from_frames(closed, matrix)


def _build_panel_curves(base_curves: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    curves = base_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    base = curves[["requested_start_month", "date", "account_equity"]].rename(columns={"account_equity": "equity"})
    base["variant"] = "stage013_engine"
    parts = [base[["variant", "requested_start_month", "date", "equity"]]]
    unmatched = 0
    curve_dates = set(zip(curves["requested_start_month"].astype(str), curves["date"]))
    for variant in CANDIDATE_VARIANTS:
        selected = lot_deltas[lot_deltas["candidate_variant"].eq(variant)].copy()
        daily_delta = (
            selected.groupby(["requested_start_month", "exit_date"], dropna=False)["stage070_proxy_delta_pnl"]
            .sum()
            .reset_index()
            if not selected.empty
            else pd.DataFrame(columns=["requested_start_month", "exit_date", "stage070_proxy_delta_pnl"])
        )
        for row in daily_delta.to_dict("records"):
            if (str(row["requested_start_month"]), row["exit_date"]) not in curve_dates:
                unmatched += 1
        merged = curves.merge(
            daily_delta.rename(columns={"exit_date": "date", "stage070_proxy_delta_pnl": "daily_delta"}),
            on=["requested_start_month", "date"],
            how="left",
        )
        merged["daily_delta"] = pd.to_numeric(merged["daily_delta"], errors="coerce").fillna(0.0)
        frames: list[pd.DataFrame] = []
        for _, group in merged.groupby("requested_start_month", sort=True):
            g = group.sort_values("date").copy()
            g["equity"] = g["account_equity"] + g["daily_delta"].cumsum()
            g["variant"] = variant
            frames.append(g[["variant", "requested_start_month", "date", "equity"]])
        if frames:
            parts.append(pd.concat(frames, ignore_index=True, sort=False))
    panel = pd.concat(parts, ignore_index=True, sort=False)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    return panel.sort_values(["variant", "requested_start_month", "date"]).reset_index(drop=True), unmatched


def _summarize_curve(curve: pd.DataFrame) -> dict[str, Any]:
    data = curve.sort_values("date").copy()
    equity = pd.to_numeric(data["equity"], errors="coerce")
    return {
        "variant": str(data["variant"].iloc[0]),
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(_drawdown_pct(equity).min()),
        "sharpe": _sharpe_from_equity(equity),
    }


def _source_summary(panel_curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in panel_curves.groupby(["variant", "requested_start_month"], sort=True):
        rows.append(_summarize_curve(group))
    return pd.DataFrame(rows).sort_values(["variant", "requested_start_month"]).reset_index(drop=True)


def _goal_audit(panel_curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    curves = panel_curves.copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["equity"] = pd.to_numeric(curves["equity"], errors="coerce")
    curves = curves.dropna(subset=["date", "equity"]).sort_values(["variant", "requested_start_month", "date"])
    return s009._run_audit(curves)


def _retention(source_summary: pd.DataFrame) -> pd.DataFrame:
    base_stage006 = _read_csv(BASE_STAGE006_SUMMARY_PATH)
    base_stage006 = base_stage006[["requested_start_month", "total_return_pct"]].rename(
        columns={"total_return_pct": "total_return_pct_base_stage006"}
    )
    stage013 = source_summary[source_summary["variant"].eq("stage013_engine")][
        ["requested_start_month", "total_return_pct"]
    ].rename(columns={"total_return_pct": "total_return_pct_stage013"})
    rows = []
    for variant in CANDIDATE_VARIANTS:
        candidate = source_summary[source_summary["variant"].eq(variant)][
            ["requested_start_month", "total_return_pct"]
        ].rename(columns={"total_return_pct": "candidate_total_return_pct"})
        merged = base_stage006.merge(stage013, on="requested_start_month", how="inner").merge(
            candidate, on="requested_start_month", how="inner"
        )
        merged["variant"] = variant
        merged["vs_base_stage006_return_ratio"] = (
            merged["candidate_total_return_pct"]
            / pd.to_numeric(merged["total_return_pct_base_stage006"], errors="coerce").replace(0.0, np.nan)
        )
        merged["vs_stage013_return_ratio"] = (
            merged["candidate_total_return_pct"]
            / pd.to_numeric(merged["total_return_pct_stage013"], errors="coerce").replace(0.0, np.nan)
        )
        merged["passes_80pct_retention_vs_base_stage006"] = merged["vs_base_stage006_return_ratio"].ge(0.80).astype("int64")
        merged["passes_80pct_retention_vs_stage013"] = merged["vs_stage013_return_ratio"].ge(0.80).astype("int64")
        rows.append(merged)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _variant_summary(
    source_summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    retention: pd.DataFrame,
    audit: dict[str, Any],
) -> pd.DataFrame:
    base_source = source_summary[source_summary["variant"].eq("stage013_engine")].set_index("requested_start_month")
    rows = []
    for variant in CANDIDATE_VARIANTS:
        source = source_summary[source_summary["variant"].eq(variant)].copy()
        source_idx = source.set_index("requested_start_month")
        common = source_idx.index.intersection(base_source.index)
        return_delta = source_idx.loc[common, "total_return_pct"] - base_source.loc[common, "total_return_pct"]
        maxdd_delta = source_idx.loc[common, "max_dd_pct"] - base_source.loc[common, "max_dd_pct"]
        all_gt1y = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")]
        final = aggregate[aggregate["variant"].eq(variant) & aggregate["audit_scope"].eq("start_to_2026_06_30_only")]
        ret = retention[retention["variant"].eq(variant)]
        rows.append(
            {
                "variant": variant,
                "selected_lots": audit.get(f"{variant}_selected_lots", 0),
                "selected_open_trades": audit.get(f"{variant}_selected_open_trades", 0),
                "selected_realized_pnl": audit.get(f"{variant}_selected_realized_pnl", 0.0),
                "total_proxy_delta_pnl": audit.get(f"{variant}_total_proxy_delta_pnl", 0.0),
                "min_return_pct": float(source["total_return_pct"].min()) if not source.empty else np.nan,
                "median_return_pct": float(source["total_return_pct"].median()) if not source.empty else np.nan,
                "worst_max_dd_pct": float(source["max_dd_pct"].min()) if not source.empty else np.nan,
                "median_sharpe": float(source["sharpe"].median()) if not source.empty else np.nan,
                "return_improved_count_vs_stage013": int(return_delta.gt(EPS).sum()),
                "return_worse_count_vs_stage013": int(return_delta.lt(-EPS).sum()),
                "maxdd_improved_count_vs_stage013": int(maxdd_delta.gt(EPS).sum()),
                "maxdd_worse_count_vs_stage013": int(maxdd_delta.lt(-EPS).sum()),
                "all_gt1y_window_count": int(all_gt1y["window_count"].sum()) if not all_gt1y.empty else 0,
                "all_gt1y_negative_count": int(all_gt1y["negative_count"].sum()) if not all_gt1y.empty else 0,
                "all_gt1y_min_return_pct": float(all_gt1y["min_return_pct"].min()) if not all_gt1y.empty else np.nan,
                "to_final_negative_count": int(final["negative_count"].sum()) if not final.empty else 0,
                "to_final_min_return_pct": float(final["min_return_pct"].min()) if not final.empty else np.nan,
                "retention_vs_base_pass_count": int(ret["passes_80pct_retention_vs_base_stage006"].sum()) if not ret.empty else 0,
                "retention_vs_stage013_pass_count": int(ret["passes_80pct_retention_vs_stage013"].sum()) if not ret.empty else 0,
                "retention_rows": int(len(ret)),
            }
        )
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["all_gt1y_negative_count", "all_gt1y_min_return_pct", "median_return_pct"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def _decision(variant_summary: pd.DataFrame, audit: dict[str, Any], unmatched_delta_dates: int) -> dict[str, Any]:
    stage013_negative = 330947
    passing = variant_summary[
        variant_summary["all_gt1y_negative_count"].eq(0)
        & variant_summary["retention_vs_base_pass_count"].eq(variant_summary["retention_rows"])
    ].copy()
    improving = variant_summary[
        variant_summary["all_gt1y_negative_count"].lt(stage013_negative)
        & variant_summary["retention_vs_base_pass_count"].eq(variant_summary["retention_rows"])
    ].copy()
    if not passing.empty:
        decision = "stage070_has_proxy_goal_candidate_requires_true_engine"
        next_stage = "freeze_best_panel_candidate_true_engine"
    elif not improving.empty:
        decision = "stage070_sibling_panel_partial_improvement_no_goal"
        next_stage = "do_not_tune_panel_candidates_turn_to_failure_attribution_or_account_layer"
    else:
        decision = "stage070_sibling_panel_no_candidate_stop_stage068_add_risk"
        next_stage = "turn_to_account_outer_layer_or_new_pit_information"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_variants": CANDIDATE_VARIANTS,
        "add_risk_fraction": ADD_RISK_FRACTION,
        "decision": decision,
        "next_stage": next_stage,
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "audit_type": "stage013_closed_lot_read_only_stage068_sibling_panel",
        "stage013_reference_all_gt1y_negative_count": stage013_negative,
        "best_variant": variant_summary.iloc[0].to_dict() if not variant_summary.empty else {},
        "variant_count": int(len(variant_summary)),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "triggered_ab_experiment": True,
        "external_research_judgment": (
            "Stage070 只比较 Stage068 已通过的低自由度 new composite，同一固定 25% 非挤占风险；"
            "这不是 topN/阈值/品种方向扫参。若面板仍不达标，应停止 Stage068 加风险形状。"
        ),
        "overfit_reflection_before": (
            "否。候选集合在 Stage068 已冻结，本阶段不新增阈值、不改风险比例、不加入诊断项。"
        ),
        "overfit_reflection_after": (
            "否。结果只用于判断 Stage068 加风险形状是否整体有目标价值；不能根据排名继续调参。"
        ),
        "continue_value_before": (
            "有。Stage069 最强均值候选只部分改善，需要确认 sibling 候选是否更贴合目标左尾。"
        ),
        "continue_value_after": (
            "若无候选清零严格负窗口，则继续价值转向失败归因、账户外层或新 PIT 信息源，不继续救 Stage068 组合。"
        ),
        **audit,
        "outputs": {
            "lot_deltas": str(LOT_DELTAS_PATH),
            "panel_curves": str(PANEL_CURVES_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "goal_aggregate": str(GOAL_AGGREGATE_PATH),
            "goal_worst_windows": str(GOAL_WORST_WINDOWS_PATH),
            "retention": str(RETENTION_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(decision: dict[str, Any], variant_summary: pd.DataFrame, worst: pd.DataFrame) -> None:
    lines = [
        "# Stage070 - Stage068 sibling composite 加风险面板",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision['next_stage']}`",
        "- 阶段性质：closed-lot 只读面板；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        "- 候选：Stage068 已通过的 3 个 new composite；固定 `+25%` 非挤占风险。",
        "",
        "## 结果摘要",
        "",
        _md_table(variant_summary, max_rows=20),
        "",
        "## 最差窗口",
        "",
        _md_table(worst.head(24), max_rows=24),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage070_super_quality_sibling_panel.md"
    report = REPORT_PATH.read_text(encoding="utf-8")
    header = f"""# Stage070 - Stage068 sibling composite 加风险面板

- 记录时间：`{timestamp.isoformat(timespec='minutes')}`
- line_id：`{LINE_ID}`
- 当前模式：`day`
- model_tag：`{MODEL_TAG}`
- 是否重要突破版本：`否`
- 是否触发A/B：`是，A/C sibling panel proxy`
- 决策：`{decision['decision']}`

## 本次版本变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage070_super_quality_sibling_panel.py`
- 新增测试：`tests/test_rebuilt_c9_stage070_super_quality_sibling_panel.py`
- 新增参数：`candidate_variants={','.join(CANDIDATE_VARIANTS)}`、`ADD_RISK_FRACTION=0.25`。
- 修改参数：无，Stage013/Stage006/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：Stage068 sibling composite closed-lot 只读 proxy 面板；不是真实组合引擎。
- 本阶段不连接 CTP，不调用订单 API，不改实盘。

## 外部调研与判断

- {decision['external_research_judgment']}

"""
    path.write_text(header + report, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    lot_deltas, audit = _build_panel_lot_deltas()
    base_curves = _read_csv(STAGE013_CURVES_PATH, parse_dates=["date"])
    panel_curves, unmatched = _build_panel_curves(base_curves, lot_deltas)
    source_summary = _source_summary(panel_curves)
    aggregate, _to_final, _fixed, worst = _goal_audit(panel_curves)
    retention = _retention(source_summary)
    variant_summary = _variant_summary(source_summary, aggregate, retention, audit)
    decision = _decision(variant_summary, audit, unmatched)

    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    panel_curves.to_csv(PANEL_CURVES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(GOAL_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(GOAL_WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, variant_summary, worst)
    stage_record = _write_stage_record(decision)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
