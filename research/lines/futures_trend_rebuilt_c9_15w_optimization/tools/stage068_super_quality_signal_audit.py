from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage068"
MODEL_TAG = "stage068_super_quality_signal_audit_v1"
STAGE_SLUG = "stage068_super_quality_signal_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage068_super_quality_signal_audit"

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"
STAGE038_FOLD_SUMMARY_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_fold_summary_{STAGE038_TAG}.csv"
STAGE038_CONDITION_SUMMARY_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_condition_oos_summary_{STAGE038_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FOLD_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fold_detail_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MIN_COUNT = 120
MIN_SOURCE_COUNT = 8
MIN_YEAR_COUNT = 4
MIN_PRODUCT_COUNT = 8
MIN_OOS_FOLDS = 3
MIN_MEAN_PNL_LIFT = 1.2

EXTERNAL_RESEARCH_LINKS = [
    "https://rpc.cfainstitute.org/research/foundation/2025/chapter-8-machine-learning-commodity-futures",
    "https://ideas.repec.org/a/kap/fmktpm/v35y2021i4d10.1007_s11408-021-00385-5.html",
    "https://blog.quantinsti.com/cross-validation-embargo-purging-combinatorial/",
]


@dataclass(frozen=True)
class Stage068CandidateSpec:
    name: str
    description: str
    feature_family: str
    mask: pd.Series
    promotion_eligible: bool
    new_composite: bool
    notes: str = ""


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
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _stage068_assign_oos_folds(
    matrix: pd.DataFrame,
    fold_summary: pd.DataFrame,
    *,
    date_column: str = "entry_date",
) -> pd.DataFrame:
    result = matrix.copy()
    result[date_column] = pd.to_datetime(result[date_column], errors="coerce").dt.normalize()
    result["stage038_oos_fold"] = ""
    if result.empty or fold_summary.empty:
        return result
    for _, fold in fold_summary.iterrows():
        split_id = str(fold.get("split_id", "")).strip()
        test_start = pd.to_datetime(fold.get("test_start"), errors="coerce")
        test_end = pd.to_datetime(fold.get("test_end"), errors="coerce")
        if not split_id or pd.isna(test_start) or pd.isna(test_end):
            continue
        mask = result[date_column].ge(test_start.normalize()) & result[date_column].le(test_end.normalize())
        result.loc[mask, "stage038_oos_fold"] = split_id
    return result


def _prepare_matrix(matrix: pd.DataFrame, fold_summary: pd.DataFrame) -> pd.DataFrame:
    frame = _stage068_assign_oos_folds(matrix, fold_summary)
    frame["entry_date"] = pd.to_datetime(frame["entry_date"], errors="coerce").dt.normalize()
    if "entry_year" not in frame.columns:
        frame["entry_year"] = frame["entry_date"].dt.year
    for column in [
        "full_market_ai_top8",
        "full_market_consensus_top8",
        "ai_rank_1_3",
        "ai_rank_1_6",
        "account_injured",
        "account_clean",
        "selected_volume_gt1",
        "oi_confirmed",
        "loss_streak_0",
        "active_positions_ge3",
        "big_winner",
    ]:
        frame[column] = _to_bool(frame.get(column, False), index=frame.index)
    frame["realized_pnl"] = _num(frame, "realized_pnl", 0.0).fillna(0.0)
    frame["r_multiple_agg"] = _num(frame, "r_multiple_agg")
    return frame


def _candidate_specs(frame: pd.DataFrame) -> list[Stage068CandidateSpec]:
    index = frame.index
    full_ai_top8 = _to_bool(frame.get("full_market_ai_top8", False), index=index)
    consensus_top8 = _to_bool(frame.get("full_market_consensus_top8", False), index=index)
    rank_1_3 = _to_bool(frame.get("ai_rank_1_3", False), index=index)
    rank_1_6 = _to_bool(frame.get("ai_rank_1_6", False), index=index)
    account_injured = _to_bool(frame.get("account_injured", False), index=index)
    account_clean = _to_bool(frame.get("account_clean", False), index=index)
    selected_volume_gt1 = _to_bool(frame.get("selected_volume_gt1", False), index=index)
    oi_confirmed = _to_bool(frame.get("oi_confirmed", False), index=index)
    loss_streak_0 = _to_bool(frame.get("loss_streak_0", False), index=index)
    active_positions_lt3 = ~_to_bool(frame.get("active_positions_ge3", False), index=index)

    return [
        Stage068CandidateSpec(
            "full_market_ai_top8",
            "Stage038 已识别的 full-market AI top8 单条件",
            "stage038_single",
            full_ai_top8,
            True,
            False,
            "重复 Stage038 的主候选，只作为本阶段比较锚点。",
        ),
        Stage068CandidateSpec(
            "ai_rank_1_6",
            "Stage182 AI rank 1-6 单条件",
            "stage038_single",
            rank_1_6,
            True,
            False,
            "重复 Stage038 的宽 AI 质量层。",
        ),
        Stage068CandidateSpec(
            "account_injured",
            "账户受伤状态单条件",
            "stage038_single",
            account_injured,
            False,
            False,
            "账户状态更像恢复线索，不直接作为 alpha 加风险条件。",
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_ai_rank_1_6",
            "full-market AI top8 且当前月 AI rank 1-6",
            "ai_composite",
            full_ai_top8 & rank_1_6,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_ai_rank_1_3",
            "full-market AI top8 且当前月 AI rank 1-3",
            "ai_composite",
            full_ai_top8 & rank_1_3,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_account_injured",
            "full-market AI top8 且账户受伤",
            "ai_account_composite",
            full_ai_top8 & account_injured,
            True,
            True,
            "只判断高质量信号是否能覆盖恢复状态，不等于账户受伤时无脑加风险。",
        ),
        Stage068CandidateSpec(
            "ai_rank_1_6_and_account_injured",
            "AI rank 1-6 且账户受伤",
            "ai_account_composite",
            rank_1_6 & account_injured,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_ai_rank_1_6_account_injured",
            "full-market AI top8 + AI rank 1-6 + 账户受伤",
            "ai_account_composite",
            full_ai_top8 & rank_1_6 & account_injured,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_account_clean",
            "full-market AI top8 且账户干净",
            "ai_account_composite",
            full_ai_top8 & account_clean,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_loss_streak_0",
            "full-market AI top8 且 loss_streak=0",
            "ai_account_composite",
            full_ai_top8 & loss_streak_0,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_active_positions_lt3",
            "full-market AI top8 且入场前持仓数<3",
            "ai_account_composite",
            full_ai_top8 & active_positions_lt3,
            True,
            True,
        ),
        Stage068CandidateSpec(
            "full_market_consensus_top8",
            "full-market AI top8 且 simple top8 共识",
            "full_market_watch",
            consensus_top8,
            False,
            False,
            "Stage038 已显示均值很高但年份/fold 太少，继续作为观察组。",
        ),
        Stage068CandidateSpec(
            "full_market_consensus_top8_and_ai_rank_1_6",
            "full-market 共识 top8 且 AI rank 1-6",
            "full_market_watch",
            consensus_top8 & rank_1_6,
            False,
            True,
            "共识样本过稀，本阶段不允许直接晋级。",
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_selected_volume_gt1",
            "full-market AI top8 且真实计划手数>1",
            "budget_diagnostic",
            full_ai_top8 & selected_volume_gt1,
            False,
            True,
            "selected_volume 是预算结果，不应单独当 alpha 信号。",
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_and_not_oi_confirmed",
            "full-market AI top8 且非 OI-confirmed",
            "oi_diagnostic",
            full_ai_top8 & ~oi_confirmed,
            False,
            True,
            "Stage060-062 已反证继续救 OI 规则，本项只诊断不晋级。",
        ),
        Stage068CandidateSpec(
            "ai_rank_1_6_and_not_oi_confirmed",
            "AI rank 1-6 且非 OI-confirmed",
            "oi_diagnostic",
            rank_1_6 & ~oi_confirmed,
            False,
            True,
            "Stage060-062 已反证继续救 OI 规则，本项只诊断不晋级。",
        ),
        Stage068CandidateSpec(
            "full_market_ai_top8_ai_rank_1_6_not_oi_confirmed",
            "full-market AI top8 + AI rank 1-6 + 非 OI-confirmed",
            "oi_diagnostic",
            full_ai_top8 & rank_1_6 & ~oi_confirmed,
            False,
            True,
            "Stage060-062 已反证继续救 OI 规则，本项只诊断不晋级。",
        ),
    ]


def _base_stats(frame: pd.DataFrame) -> dict[str, float]:
    pnl = _num(frame, "realized_pnl", 0.0).fillna(0.0)
    r_multiple = _num(frame, "r_multiple_agg")
    return {
        "count": float(len(frame)),
        "total_pnl": float(pnl.sum()),
        "mean_pnl": float(pnl.mean()) if len(frame) else 0.0,
        "median_r": float(r_multiple.median()) if r_multiple.notna().any() else np.nan,
        "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if len(frame) else 0.0,
        "big_win_rate_pct": float(_to_bool(frame.get("big_winner", False), index=frame.index).mean() * 100.0)
        if len(frame)
        else 0.0,
    }


def _positive_pnl_concentration(pnl: pd.Series) -> float:
    positive = pnl[pnl.gt(0.0)].sort_values(ascending=False)
    positive_total = float(positive.sum())
    if positive.empty or positive_total <= 0.0:
        return 0.0
    top_n = max(1, int(math.ceil(len(positive) * 0.10)))
    return float(positive.head(top_n).sum() / positive_total * 100.0)


def _failure_reasons(row: dict[str, Any]) -> str:
    reasons: list[str] = []
    if not bool(row["promotion_eligible"]):
        reasons.append("not_promotion_eligible")
    if row["count"] < MIN_COUNT:
        reasons.append("count")
    if row["source_count"] < MIN_SOURCE_COUNT:
        reasons.append("source_count")
    if row["year_count"] < MIN_YEAR_COUNT:
        reasons.append("year_count")
    if row["product_count"] < MIN_PRODUCT_COUNT:
        reasons.append("product_count")
    if row["oos_test_fold_count"] < MIN_OOS_FOLDS:
        reasons.append("oos_fold_count")
    if row["oos_positive_fold_count"] != row["oos_test_fold_count"]:
        reasons.append("oos_positive_fold_count")
    if pd.isna(row["oos_min_fold_pnl"]) or row["oos_min_fold_pnl"] <= 0.0:
        reasons.append("oos_min_fold_pnl")
    if row["positive_year_count"] != row["year_count"]:
        reasons.append("positive_year_count")
    if pd.isna(row["worst_year_pnl"]) or row["worst_year_pnl"] <= 0.0:
        reasons.append("worst_year_pnl")
    if row["total_pnl"] <= 0.0:
        reasons.append("total_pnl")
    if pd.isna(row["mean_pnl_lift_vs_base"]) or row["mean_pnl_lift_vs_base"] < MIN_MEAN_PNL_LIFT:
        reasons.append("mean_pnl_lift")
    return ",".join(reasons)


def _stage068_condition_summary(
    frame: pd.DataFrame,
    specs: list[Stage068CandidateSpec],
    *,
    min_count: int = MIN_COUNT,
    min_source_count: int = MIN_SOURCE_COUNT,
    min_year_count: int = MIN_YEAR_COUNT,
    min_product_count: int = MIN_PRODUCT_COUNT,
    min_oos_folds: int = MIN_OOS_FOLDS,
    min_mean_pnl_lift: float = MIN_MEAN_PNL_LIFT,
) -> pd.DataFrame:
    base = _base_stats(frame)
    rows: list[dict[str, Any]] = []
    for spec in specs:
        mask = spec.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask].copy()
        pnl = _num(subset, "realized_pnl", 0.0).fillna(0.0)
        r_multiple = _num(subset, "r_multiple_agg")
        fold_frame = subset[subset["stage038_oos_fold"].astype(str).ne("")]
        fold_pnl = fold_frame.groupby("stage038_oos_fold")["realized_pnl"].sum() if not fold_frame.empty else pd.Series(dtype=float)
        fold_count = fold_frame.groupby("stage038_oos_fold")["realized_pnl"].size() if not fold_frame.empty else pd.Series(dtype=int)
        year_pnl = subset.groupby("entry_year")["realized_pnl"].sum() if not subset.empty else pd.Series(dtype=float)
        source_count = int(subset["requested_start_month"].nunique()) if "requested_start_month" in subset.columns else 0
        year_count = int(subset["entry_year"].nunique()) if "entry_year" in subset.columns else 0
        product_count = int(subset["product_vt_symbol"].nunique()) if "product_vt_symbol" in subset.columns else 0
        total_pnl = float(pnl.sum()) if len(subset) else 0.0
        mean_pnl = float(pnl.mean()) if len(subset) else 0.0
        row = {
            "condition": spec.name,
            "description": spec.description,
            "feature_family": spec.feature_family,
            "promotion_eligible": bool(spec.promotion_eligible),
            "new_composite": bool(spec.new_composite),
            "notes": spec.notes,
            "count": int(len(subset)),
            "coverage_pct": float(len(subset) / len(frame) * 100.0) if len(frame) else 0.0,
            "source_count": source_count,
            "year_count": year_count,
            "product_count": product_count,
            "total_pnl": total_pnl,
            "pnl_share_pct": float(total_pnl / base["total_pnl"] * 100.0) if base["total_pnl"] else np.nan,
            "mean_pnl": mean_pnl,
            "mean_pnl_lift_vs_base": float(mean_pnl / base["mean_pnl"]) if base["mean_pnl"] else np.nan,
            "median_r": float(r_multiple.median()) if r_multiple.notna().any() else np.nan,
            "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if len(subset) else 0.0,
            "win_rate_lift_pp": float(pnl.gt(0.0).mean() * 100.0 - base["win_rate_pct"]) if len(subset) else np.nan,
            "big_win_rate_pct": float(_to_bool(subset.get("big_winner", False), index=subset.index).mean() * 100.0)
            if len(subset)
            else 0.0,
            "big_win_rate_lift_pp": (
                float(_to_bool(subset.get("big_winner", False), index=subset.index).mean() * 100.0 - base["big_win_rate_pct"])
                if len(subset)
                else np.nan
            ),
            "positive_pnl_top10_share_pct": _positive_pnl_concentration(pnl),
            "oos_test_fold_count": int(len(fold_pnl)),
            "oos_positive_fold_count": int(fold_pnl.gt(0.0).sum()) if len(fold_pnl) else 0,
            "oos_min_fold_pnl": float(fold_pnl.min()) if len(fold_pnl) else np.nan,
            "oos_total_test_pnl": float(fold_pnl.sum()) if len(fold_pnl) else 0.0,
            "oos_min_fold_count": int(fold_count.min()) if len(fold_count) else 0,
            "positive_year_count": int(year_pnl.gt(0.0).sum()) if len(year_pnl) else 0,
            "worst_year_pnl": float(year_pnl.min()) if len(year_pnl) else np.nan,
            "best_year_pnl": float(year_pnl.max()) if len(year_pnl) else np.nan,
        }
        failure_reasons = []
        if not row["promotion_eligible"]:
            failure_reasons.append("not_promotion_eligible")
        if row["count"] < min_count:
            failure_reasons.append("count")
        if row["source_count"] < min_source_count:
            failure_reasons.append("source_count")
        if row["year_count"] < min_year_count:
            failure_reasons.append("year_count")
        if row["product_count"] < min_product_count:
            failure_reasons.append("product_count")
        if row["oos_test_fold_count"] < min_oos_folds:
            failure_reasons.append("oos_fold_count")
        if row["oos_positive_fold_count"] != row["oos_test_fold_count"]:
            failure_reasons.append("oos_positive_fold_count")
        if pd.isna(row["oos_min_fold_pnl"]) or row["oos_min_fold_pnl"] <= 0.0:
            failure_reasons.append("oos_min_fold_pnl")
        if row["positive_year_count"] != row["year_count"]:
            failure_reasons.append("positive_year_count")
        if pd.isna(row["worst_year_pnl"]) or row["worst_year_pnl"] <= 0.0:
            failure_reasons.append("worst_year_pnl")
        if row["total_pnl"] <= 0.0:
            failure_reasons.append("total_pnl")
        if pd.isna(row["mean_pnl_lift_vs_base"]) or row["mean_pnl_lift_vs_base"] < min_mean_pnl_lift:
            failure_reasons.append("mean_pnl_lift")
        row["failure_reasons"] = ",".join(failure_reasons)
        row["super_quality_candidate"] = not failure_reasons
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        [
            "super_quality_candidate",
            "promotion_eligible",
            "new_composite",
            "mean_pnl_lift_vs_base",
            "oos_min_fold_pnl",
            "count",
        ],
        ascending=[False, False, False, False, False, False],
    ).reset_index(drop=True)


def _condition_fold_detail(frame: pd.DataFrame, specs: list[Stage068CandidateSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        mask = spec.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask & frame["stage038_oos_fold"].astype(str).ne("")].copy()
        if subset.empty:
            continue
        grouped = subset.groupby("stage038_oos_fold", dropna=False)
        for fold, group in grouped:
            pnl = _num(group, "realized_pnl", 0.0).fillna(0.0)
            rows.append(
                {
                    "condition": spec.name,
                    "stage038_oos_fold": fold,
                    "count": int(len(group)),
                    "total_pnl": float(pnl.sum()),
                    "mean_pnl": float(pnl.mean()) if len(group) else 0.0,
                    "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if len(group) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _condition_year_detail(frame: pd.DataFrame, specs: list[Stage068CandidateSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        mask = spec.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask].copy()
        if subset.empty:
            continue
        grouped = subset.groupby("entry_year", dropna=False)
        for year, group in grouped:
            pnl = _num(group, "realized_pnl", 0.0).fillna(0.0)
            rows.append(
                {
                    "condition": spec.name,
                    "entry_year": int(year) if pd.notna(year) else 0,
                    "count": int(len(group)),
                    "total_pnl": float(pnl.sum()),
                    "mean_pnl": float(pnl.mean()) if len(group) else 0.0,
                    "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if len(group) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _stage068_decision_from_summary(summary: pd.DataFrame, *, matrix_rows: int) -> dict[str, Any]:
    if summary.empty:
        return {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "decision": "stage068_no_candidate_summary_keep_readonly",
            "matrix_rows": int(matrix_rows),
            "stable_candidate_count": 0,
            "new_composite_candidate_count": 0,
            "best_new_composite_candidate": {},
            "best_overall_candidate": {},
        }
    stable = summary[summary["super_quality_candidate"].astype(bool)].copy()
    new_stable = stable[stable["new_composite"].astype(bool)].copy()
    if not new_stable.empty:
        decision = "stage068_has_new_composite_super_quality_candidate_needs_proxy"
        next_stage = "stage069_freeze_one_composite_ai_account_proxy_true_engine_no_param_sweep"
    elif not stable.empty:
        decision = "stage068_only_reconfirms_stage038_single_candidates_keep_readonly"
        next_stage = "do_not_repeat_full_market_top8_proxy_turn_to_account_layer_or_new_pit_source"
    else:
        decision = "stage068_no_low_degree_super_quality_candidate_keep_readonly"
        next_stage = "turn_to_account_outer_layer_or_new_point_in_time_information_source"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "next_stage": next_stage,
        "matrix_rows": int(matrix_rows),
        "stable_candidate_count": int(len(stable)),
        "new_composite_candidate_count": int(len(new_stable)),
        "stable_candidates": stable["condition"].head(20).tolist(),
        "new_composite_candidates": new_stable["condition"].head(20).tolist(),
        "best_new_composite_candidate": new_stable.iloc[0].to_dict() if not new_stable.empty else {},
        "best_overall_candidate": stable.iloc[0].to_dict() if not stable.empty else {},
    }


def _plot_candidate_chart(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    shown = summary.head(14).iloc[::-1].copy()
    colors = ["#2f855a" if bool(value) else "#4a5568" for value in shown["super_quality_candidate"]]
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(shown["condition"], shown["mean_pnl_lift_vs_base"], color=colors)
    ax.axvline(1.0, color="#a0aec0", linewidth=1.0)
    ax.axvline(MIN_MEAN_PNL_LIFT, color="#dd6b20", linewidth=1.0, linestyle="--")
    ax.set_xlabel("mean PnL lift vs all opened trades")
    ax.set_title("Stage068 fixed candidate signal quality audit")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, fold_detail: pd.DataFrame) -> None:
    lines = [
        "# Stage068 - AI 超高质量信号组合只读审计",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision.get('next_stage', '')}`",
        "- 本阶段只读：不改官方 C9/15w，不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- CFA commodity ML 资料支持商品期货里使用有理论约束、可解释、点时可见的 ML 信号。",
        "- 商品期货 trend-following/cross-sectional trend 研究支持横截面排序有价值，但不能替代本仓执行约束下的 OOS 审计。",
        "- purged/embargo cross-validation 资料提醒金融时间序列必须避免泄漏和相邻样本污染；本阶段沿用 Stage038 时间 fold，只看预声明组合。",
        f"- 参考链接：{', '.join(EXTERNAL_RESEARCH_LINKS)}",
        "",
        "## 样本与门槛",
        "",
        f"- 输入矩阵：`{STAGE038_FEATURE_MATRIX_PATH}`",
        f"- 输入 fold：`{STAGE038_FOLD_SUMMARY_PATH}`",
        f"- matrix rows：`{decision['matrix_rows']}`",
        f"- 门槛：count>={MIN_COUNT}, source>={MIN_SOURCE_COUNT}, year>={MIN_YEAR_COUNT}, "
        f"product>={MIN_PRODUCT_COUNT}, OOS folds>={MIN_OOS_FOLDS}, mean lift>={MIN_MEAN_PNL_LIFT}，且每个 OOS fold/观察年份均为正。",
        "",
        "## 候选汇总",
        "",
        _md_table(
            summary[
                [
                    "condition",
                    "promotion_eligible",
                    "new_composite",
                    "count",
                    "year_count",
                    "product_count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "win_rate_lift_pp",
                    "big_win_rate_lift_pp",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "positive_year_count",
                    "worst_year_pnl",
                    "super_quality_candidate",
                    "failure_reasons",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## OOS fold 明细",
        "",
        _md_table(fold_detail.head(40), max_rows=40),
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否。本阶段冻结 Stage038 已可见字段和少数低自由度组合，不按收益扫 rank/topN/年份/品种。",
        "- 运行后过拟合反思：否。输出只决定是否有资格进入下一步 proxy/真引擎，不直接改实盘；OI/selected_volume 相关组合即使好看也只作诊断。",
        "- 运行前继续价值反思：有。用户目标明确要求 AI 选品进一步识别超高质量信号，加风险前必须先证明质量层存在。",
        "- 运行后继续价值反思：看是否出现 new_composite_candidate；若没有，应该转账户外层或新 PIT 信息源。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    stage_path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage068_super_quality_signal_audit.md"
    best_new = decision.get("best_new_composite_candidate") or {}
    lines = [
        "# Stage068 - AI 超高质量信号组合只读审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- 工作区/分支：`{REPO_ROOT}`",
        "- 阶段性质：只读 PIT/OOS 信号质量审计",
        "- 是否重要突破：`否`",
        "- 是否触发A/B：`否`",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：CFA commodity ML、commodity futures trend-following/cross-sectional trend、purged/embargo CV。",
        "- 我的判断：AI 选品优化必须用点时可见、低自由度、OOS 全正的组合；不能把单年高均值或删除前记忆当作可交易规则。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage068_super_quality_signal_audit.py`",
        f"- 新增测试：`tests/test_rebuilt_c9_stage068_super_quality_signal_audit.py`",
        "- 修改脚本：无正式策略脚本。",
        "- 删除脚本：无。",
        f"- 新增参数：`MIN_COUNT={MIN_COUNT}`、`MIN_SOURCE_COUNT={MIN_SOURCE_COUNT}`、"
        f"`MIN_YEAR_COUNT={MIN_YEAR_COUNT}`、`MIN_PRODUCT_COUNT={MIN_PRODUCT_COUNT}`、"
        f"`MIN_OOS_FOLDS={MIN_OOS_FOLDS}`、`MIN_MEAN_PNL_LIFT={MIN_MEAN_PNL_LIFT}`。",
        "- 修改参数：无正式交易参数。",
        "- 删除参数：无。",
        "",
        "## 回测/归因参数",
        "",
        "- 数据区间：复用 Stage038 `2020-01-02` 到 `2026-06-24` opened flat-entry 聚合矩阵。",
        "- 账户规模：不适用，本阶段非资金曲线回测。",
        "- 成本口径：复用 Stage038 realized PnL，非新增撮合。",
        "- 样本过滤：固定低自由度 AI/full-market/account 组合；OI 与 selected_volume 仅诊断不晋级。",
        "- 策略/归因口径：沿用 Stage038 OOS fold，要求每个命中 fold 和观察年份均为正。",
        "",
        "## 结果",
        "",
        "- 期末权益：不适用。",
        "- 总收益：不适用。",
        "- 最大回撤：不适用。",
        "- Sharpe：不适用。",
        "- 总滑点：不适用。",
        "- 总交易次数：不适用。",
        "- 胜率：见 summary 表。",
        f"- 其他关键指标：matrix rows `{decision['matrix_rows']}`；stable candidates `{decision['stable_candidate_count']}`；"
        f"new composite candidates `{decision['new_composite_candidate_count']}`；best new `{best_new.get('condition', '无')}`。",
        "",
        "## 候选摘要",
        "",
        _md_table(
            summary[
                [
                    "condition",
                    "promotion_eligible",
                    "new_composite",
                    "count",
                    "year_count",
                    "product_count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "worst_year_pnl",
                    "super_quality_candidate",
                    "failure_reasons",
                ]
            ],
            max_rows=18,
        ),
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- fold_detail：`{FOLD_DETAIL_PATH}`",
        f"- year_detail：`{YEAR_DETAIL_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`。",
        f"- 是否进入下一步：`{'是' if decision.get('new_composite_candidate_count', 0) else '否'}`。",
        f"- 下一步：`{decision.get('next_stage', '')}`。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否，固定 Stage038 可见字段与少数理论组合，不扫收益阈值。",
        "- 运行后判断：否，本阶段没有根据结果救参；诊断项不直接晋级。",
        "- 原因：只输出资格审计，不改实盘、不写交易规则、不连接订单链路。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有，用户目标包含 AI 高质量信号和加大风险投入，必须先证明质量层存在。",
        f"- 运行后判断：`{'有' if decision.get('new_composite_candidate_count', 0) else '有限'}`。",
        "- 原因：若 new composite 通过，下一步可冻结一个 proxy；若没有，应转账户外层或新 PIT 信息源。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是。",
        "- 是否更新 `research/registry.md`：是。",
        "- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，`memory.md` 视为非正式突破可不追加。",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    matrix = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    fold_summary = _read_csv(STAGE038_FOLD_SUMMARY_PATH)
    frame = _prepare_matrix(matrix, fold_summary)
    specs = _candidate_specs(frame)
    summary = _stage068_condition_summary(frame, specs)
    fold_detail = _condition_fold_detail(frame, specs)
    year_detail = _condition_year_detail(frame, specs)
    decision = _stage068_decision_from_summary(summary, matrix_rows=len(frame))
    decision.update(
        {
            "stage038_feature_matrix_path": str(STAGE038_FEATURE_MATRIX_PATH),
            "stage038_fold_summary_path": str(STAGE038_FOLD_SUMMARY_PATH),
            "stage038_condition_summary_path": str(STAGE038_CONDITION_SUMMARY_PATH),
            "official_live_config_changed": False,
            "ctp_connected": False,
            "order_api_calls": 0,
            "triggered_ab_experiment": False,
            "external_research_links": EXTERNAL_RESEARCH_LINKS,
            "outputs": {
                "summary": str(SUMMARY_PATH),
                "fold_detail": str(FOLD_DETAIL_PATH),
                "year_detail": str(YEAR_DETAIL_PATH),
                "chart": str(CHART_PATH),
                "decision": str(DECISION_PATH),
                "report": str(REPORT_PATH),
            },
        }
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    fold_detail.to_csv(FOLD_DETAIL_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    _plot_candidate_chart(summary)
    _write_report(decision, summary, fold_detail)
    stage_record = _write_stage_record(decision, summary)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
