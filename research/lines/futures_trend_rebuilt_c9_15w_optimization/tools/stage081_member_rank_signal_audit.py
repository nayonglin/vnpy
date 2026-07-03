from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from stage068_super_quality_signal_audit import _stage068_assign_oos_folds


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage081"
MODEL_TAG = "stage081_member_rank_signal_audit_v1"
STAGE_SLUG = "stage081_member_rank_signal_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage081_member_rank_signal_audit"

MIN_COUNT = 120
MIN_SOURCE_COUNT = 8
MIN_YEAR_COUNT = 4
MIN_PRODUCT_COUNT = 8
MIN_OOS_FOLDS = 3
MIN_MEAN_PNL_LIFT = 1.2
MIN_AVAILABLE_COVERAGE_PCT = 50.0

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FOLD_SUMMARY_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_fold_summary_{STAGE038_TAG}.csv"

STAGE080_OUTPUT_DIR = LINE_DIR / "outputs" / "stage080_member_rank_2022_backfill_feasibility"
STAGE080_PREFIX = "rebuilt_c9_stage080_member_rank_2022_backfill_feasibility"
STAGE080_TAG = "stage080_member_rank_2022_backfill_feasibility_v1"
STAGE080_JOINED_FEATURES_PATH = STAGE080_OUTPUT_DIR / f"{STAGE080_PREFIX}_after_joined_feature_matrix_{STAGE080_TAG}.csv"
STAGE080_COMBINED_RAW_PATH = STAGE080_OUTPUT_DIR / f"{STAGE080_PREFIX}_combined_raw_{STAGE080_TAG}.csv"
STAGE080_COMBINED_FEATURES_PATH = STAGE080_OUTPUT_DIR / f"{STAGE080_PREFIX}_combined_member_features_{STAGE080_TAG}.csv"

PREPARED_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prepared_matrix_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FOLD_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fold_detail_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
PRODUCT_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_detail_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

EXTERNAL_RESEARCH_LINKS = [
    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
    "https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest",
    "https://efinance.org.cn/cn/aboutme/yhy.pdf",
    "https://www.htfc.com/wz_upload/png_upload/20180330/1522397798583d90f55.pdf",
    "https://github.com/pst-group/pysystemtrade",
]


@dataclass(frozen=True)
class Stage081ConditionSpec:
    name: str
    description: str
    feature_family: str
    mask: pd.Series
    promotion_eligible: bool
    notes: str = ""


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _direction_sign(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.strip().str.lower()
    return pd.Series(np.where(text.eq("short"), -1.0, np.where(text.eq("long"), 1.0, np.nan)), index=series.index)


def add_directional_member_rank_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    index = result.index
    available = _to_bool(result.get("member_rank_available", False), index=index)
    sign = _direction_sign(result.get("direction", pd.Series("", index=index)))
    net_position = _num(result, "member_rank_net_position_ratio_top20")
    net_flow = _num(result, "member_rank_net_position_chg_ratio_top20")
    turnover = _num(result, "member_rank_turnover_pressure_ratio_top20")
    result["member_rank_available"] = available
    result["member_rank_direction_sign"] = sign
    result["member_rank_directional_net_position"] = net_position * sign
    result["member_rank_directional_net_flow"] = net_flow * sign
    result["member_rank_turnover_pressure_ratio_top20"] = turnover
    result["member_rank_net_position_aligned"] = available & result["member_rank_directional_net_position"].gt(0.0)
    result["member_rank_net_position_against"] = available & result["member_rank_directional_net_position"].lt(0.0)
    result["member_rank_net_flow_aligned"] = available & result["member_rank_directional_net_flow"].gt(0.0)
    result["member_rank_net_flow_against"] = available & result["member_rank_directional_net_flow"].lt(0.0)
    result["member_rank_net_position_and_flow_aligned"] = (
        result["member_rank_net_position_aligned"] & result["member_rank_net_flow_aligned"]
    )
    result["member_rank_net_position_or_flow_aligned"] = (
        result["member_rank_net_position_aligned"] | result["member_rank_net_flow_aligned"]
    )
    result["member_rank_turnover_high"] = available & turnover.ge(turnover.loc[available].quantile(0.75))
    result["member_rank_turnover_low"] = available & turnover.le(turnover.loc[available].quantile(0.25))
    return result


def prepare_member_rank_matrix(matrix: pd.DataFrame, fold_summary: pd.DataFrame) -> pd.DataFrame:
    result = _stage068_assign_oos_folds(matrix, fold_summary)
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    if "entry_year" not in result.columns:
        result["entry_year"] = result["entry_date"].dt.year
    result["realized_pnl"] = _num(result, "realized_pnl", 0.0).fillna(0.0)
    for column in ["full_market_ai_top8", "ai_rank_1_6", "ai_rank_1_9", "account_injured", "big_winner"]:
        result[column] = _to_bool(result.get(column, False), index=result.index)
    return add_directional_member_rank_features(result)


def member_rank_condition_specs(frame: pd.DataFrame) -> list[Stage081ConditionSpec]:
    index = frame.index
    available = _to_bool(frame.get("member_rank_available", False), index=index)
    net_aligned = _to_bool(frame.get("member_rank_net_position_aligned", False), index=index)
    net_against = _to_bool(frame.get("member_rank_net_position_against", False), index=index)
    flow_aligned = _to_bool(frame.get("member_rank_net_flow_aligned", False), index=index)
    flow_against = _to_bool(frame.get("member_rank_net_flow_against", False), index=index)
    both_aligned = _to_bool(frame.get("member_rank_net_position_and_flow_aligned", False), index=index)
    either_aligned = _to_bool(frame.get("member_rank_net_position_or_flow_aligned", False), index=index)
    turnover_high = _to_bool(frame.get("member_rank_turnover_high", False), index=index)
    turnover_low = _to_bool(frame.get("member_rank_turnover_low", False), index=index)
    ai_top8 = _to_bool(frame.get("full_market_ai_top8", False), index=index)
    ai_rank_1_6 = _to_bool(frame.get("ai_rank_1_6", False), index=index)
    account_injured = _to_bool(frame.get("account_injured", False), index=index)

    return [
        Stage081ConditionSpec(
            "member_rank_available",
            "会员排名 T+1 as-of 可用样本",
            "coverage_anchor",
            available,
            False,
            "覆盖锚点，不作为信号。",
        ),
        Stage081ConditionSpec(
            "member_rank_net_position_aligned",
            "会员前20净持仓方向与交易方向一致",
            "member_rank_position",
            net_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "member_rank_net_position_against",
            "会员前20净持仓方向与交易方向相反",
            "member_rank_position",
            net_against,
            False,
            "反向诊断，不晋级。",
        ),
        Stage081ConditionSpec(
            "member_rank_net_flow_aligned",
            "会员前20净持仓变化方向与交易方向一致",
            "member_rank_flow",
            flow_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "member_rank_net_flow_against",
            "会员前20净持仓变化方向与交易方向相反",
            "member_rank_flow",
            flow_against,
            False,
            "反向诊断，不晋级。",
        ),
        Stage081ConditionSpec(
            "member_rank_net_position_and_flow_aligned",
            "会员净持仓和净变化均与交易方向一致",
            "member_rank_position_flow",
            both_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "member_rank_net_position_or_flow_aligned",
            "会员净持仓或净变化与交易方向一致",
            "member_rank_position_flow",
            either_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "member_rank_aligned_and_turnover_high",
            "会员方向一致且 top20 turnover pressure 处于可用样本高四分位",
            "member_rank_turnover",
            either_aligned & turnover_high,
            True,
            "四分位只作固定流动性/拥挤强度诊断，不扫阈值。",
        ),
        Stage081ConditionSpec(
            "member_rank_aligned_and_turnover_low",
            "会员方向一致且 top20 turnover pressure 处于可用样本低四分位",
            "member_rank_turnover",
            either_aligned & turnover_low,
            True,
            "四分位只作固定流动性/拥挤强度诊断，不扫阈值。",
        ),
        Stage081ConditionSpec(
            "full_market_ai_top8_and_member_net_position_aligned",
            "full-market AI top8 且会员净持仓方向一致",
            "ai_member_rank_composite",
            ai_top8 & net_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "full_market_ai_top8_and_member_net_flow_aligned",
            "full-market AI top8 且会员净持仓变化方向一致",
            "ai_member_rank_composite",
            ai_top8 & flow_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "full_market_ai_top8_and_member_position_flow_aligned",
            "full-market AI top8 且会员净持仓和净变化均方向一致",
            "ai_member_rank_composite",
            ai_top8 & both_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "ai_rank_1_6_and_member_net_position_aligned",
            "AI rank 1-6 且会员净持仓方向一致",
            "ai_member_rank_composite",
            ai_rank_1_6 & net_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "ai_rank_1_6_and_member_net_flow_aligned",
            "AI rank 1-6 且会员净持仓变化方向一致",
            "ai_member_rank_composite",
            ai_rank_1_6 & flow_aligned,
            True,
        ),
        Stage081ConditionSpec(
            "account_injured_and_member_position_flow_aligned",
            "账户受伤且会员净持仓和净变化均方向一致",
            "account_member_rank_composite",
            account_injured & both_aligned,
            True,
            "账户状态组合只做恢复质量诊断，不等于账户受伤时加风险。",
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
    total = float(positive.sum())
    if positive.empty or total <= 0.0:
        return 0.0
    top_n = max(1, int(math.ceil(len(positive) * 0.10)))
    return float(positive.head(top_n).sum() / total * 100.0)


def member_rank_condition_summary(
    frame: pd.DataFrame,
    specs: list[Stage081ConditionSpec],
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
        product_pnl = subset.groupby("product_vt_symbol")["realized_pnl"].sum() if not subset.empty else pd.Series(dtype=float)
        source_count = int(subset["requested_start_month"].nunique()) if "requested_start_month" in subset.columns else 0
        year_count = int(subset["entry_year"].nunique()) if "entry_year" in subset.columns else 0
        product_count = int(subset["product_vt_symbol"].nunique()) if "product_vt_symbol" in subset.columns else 0
        total_pnl = float(pnl.sum()) if len(subset) else 0.0
        mean_pnl = float(pnl.mean()) if len(subset) else 0.0
        row: dict[str, Any] = {
            "condition": spec.name,
            "description": spec.description,
            "feature_family": spec.feature_family,
            "promotion_eligible": bool(spec.promotion_eligible),
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
            "positive_product_count": int(product_pnl.gt(0.0).sum()) if len(product_pnl) else 0,
            "worst_product_pnl": float(product_pnl.min()) if len(product_pnl) else np.nan,
        }
        failure_reasons: list[str] = []
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
        row["member_rank_signal_candidate"] = not failure_reasons
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        [
            "member_rank_signal_candidate",
            "promotion_eligible",
            "mean_pnl_lift_vs_base",
            "oos_min_fold_pnl",
            "count",
        ],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def _condition_fold_detail(frame: pd.DataFrame, specs: list[Stage081ConditionSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        mask = spec.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask & frame["stage038_oos_fold"].astype(str).ne("")].copy()
        for fold, group in subset.groupby("stage038_oos_fold", dropna=False):
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


def _condition_year_detail(frame: pd.DataFrame, specs: list[Stage081ConditionSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        mask = spec.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask].copy()
        for year, group in subset.groupby("entry_year", dropna=False):
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


def _condition_product_detail(frame: pd.DataFrame, specs: list[Stage081ConditionSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        mask = spec.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask].copy()
        for product, group in subset.groupby("product_vt_symbol", dropna=False):
            pnl = _num(group, "realized_pnl", 0.0).fillna(0.0)
            rows.append(
                {
                    "condition": spec.name,
                    "product_vt_symbol": product,
                    "count": int(len(group)),
                    "total_pnl": float(pnl.sum()),
                    "mean_pnl": float(pnl.mean()) if len(group) else 0.0,
                    "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if len(group) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def decision_from_member_rank_summary(
    summary: pd.DataFrame,
    *,
    matrix_rows: int,
    available_rows: int,
) -> dict[str, Any]:
    available_coverage_pct = float(available_rows / matrix_rows * 100.0) if matrix_rows else 0.0
    stable = summary[summary.get("member_rank_signal_candidate", pd.Series(False, index=summary.index)).astype(bool)].copy()
    if available_coverage_pct < MIN_AVAILABLE_COVERAGE_PCT:
        decision = "stage081_member_rank_coverage_too_low_keep_readonly"
        next_stage = "do_not_trade_member_rank_until_coverage_is_repaired"
    elif not stable.empty:
        decision = "stage081_member_rank_has_stable_signal_candidate_needs_proxy"
        next_stage = "stage082_freeze_one_member_rank_candidate_proxy_no_param_sweep"
    else:
        decision = "stage081_member_rank_no_stable_signal_candidate_keep_readonly"
        next_stage = "do_not_trade_member_rank_turn_to_other_pit_source_or_account_structure"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "next_stage": next_stage,
        "matrix_rows": int(matrix_rows),
        "member_rank_available_rows": int(available_rows),
        "member_rank_available_coverage_pct": available_coverage_pct,
        "stable_candidate_count": int(len(stable)),
        "stable_candidates": stable["condition"].head(20).tolist() if not stable.empty else [],
        "best_member_rank_candidate": stable.iloc[0].to_dict() if not stable.empty else {},
    }


def _plot_candidate_chart(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    shown = summary.head(14).iloc[::-1].copy()
    colors = ["#2f855a" if bool(value) else "#4a5568" for value in shown["member_rank_signal_candidate"]]
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(shown["condition"], shown["mean_pnl_lift_vs_base"], color=colors)
    ax.axvline(1.0, color="#a0aec0", linewidth=1.0)
    ax.axvline(MIN_MEAN_PNL_LIFT, color="#dd6b20", linewidth=1.0, linestyle="--")
    ax.set_xlabel("mean PnL lift vs all opened trades")
    ax.set_title("Stage081 fixed member-rank signal audit")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(decision: dict[str, Any], summary: pd.DataFrame, fold_detail: pd.DataFrame) -> None:
    lines = [
        "# Stage081 - 国内会员排名特征方向/OOS 审计",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 下一步：`{decision.get('next_stage', '')}`",
        "- 本阶段只读：不改官方 C9/15w，不改 AI 池，不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- CFTC COT 与 CME open interest 资料支持持仓结构可作为市场参与者行为信息，但强调发布频率/滞后和辅助分析属性。",
        "- 国内商品成交持仓排名研报支持用前 N 名会员净持仓、净持仓变化等因子描述主力多空力量，但参数化风险很高。",
        "- pysystemtrade 的系统化交易框架提醒交易信号必须有可复验数据、成本和风险纪律；本阶段因此只做预声明特征审计。",
        "",
        "## 覆盖与输入",
        "",
        f"- 样本行：`{decision['matrix_rows']}`。",
        f"- 会员排名可用：`{decision['member_rank_available_rows']}` = `{decision['member_rank_available_coverage_pct']:.4f}%`。",
        f"- Stage080 combined raw sha256：`{decision['source_hashes']['stage080_combined_raw_sha256']}`。",
        f"- Stage080 combined features sha256：`{decision['source_hashes']['stage080_combined_features_sha256']}`。",
        "",
        "## 候选摘要",
        "",
        _md_table(
            summary[
                [
                    "condition",
                    "member_rank_signal_candidate",
                    "count",
                    "source_count",
                    "year_count",
                    "product_count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "worst_year_pnl",
                    "failure_reasons",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## OOS fold 明细",
        "",
        _md_table(fold_detail.head(40), max_rows=40),
        "",
        "## 反思",
        "",
        "- 运行前过拟合反思：否；本阶段只验证 Stage080 补数后的预声明会员排名特征，不调交易参数。",
        "- 运行后过拟合反思：若某候选只靠局部年份/fold 或小样本高均值通过直觉筛选，就必须拒绝；只有全部稳健性门通过才进入 proxy。",
        "- 运行前继续价值反思：有；Stage080 已把左尾覆盖补到可审计水平。",
        "- 运行后继续价值反思：取决于是否存在 stable candidate；即便存在，也只能先做冻结 proxy/真引擎验真。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage081_member_rank_signal_audit.md"
    stable_count = int(decision.get("stable_candidate_count", 0))
    best = decision.get("best_member_rank_candidate", {}) or {}
    stage_path.write_text(
        "\n".join(
            [
                "# Stage081 国内会员排名特征方向/OOS 审计",
                "",
                f"- line_id：`{LINE_ID}`",
                "- 当前模式：day",
                f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
                "- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`",
                "- 阶段性质：只读信号方向/OOS 审计，不改线上、不改 AI 池、不接 CTP/SimNow。",
                "- 是否重要突破：否，除非后续 proxy/真引擎证明可改善目标。",
                "- 是否触发A/B：否。",
                "",
                "## 外部调研与判断",
                "",
                "- 参考资料：CFTC COT、CME open interest、国内商品成交持仓排名因子研报、我国商品期货持仓额信息含量研究、pysystemtrade。",
                "- 我的判断：会员排名有经济含义，但必须从净持仓方向/净变化这类低自由度特征开始，并经过 OOS、年份、品种、source 稳定性门；覆盖达标不等于信号有效。",
                "",
                "## 本次变更",
                "",
                f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage081_member_rank_signal_audit.py`。",
                f"- 新增测试：`tests/test_rebuilt_c9_stage081_member_rank_signal_audit.py`。",
                "- 修改脚本：无正式交易脚本修改。",
                "- 删除脚本：无。",
                f"- 新增参数：`MIN_COUNT={MIN_COUNT}`、`MIN_SOURCE_COUNT={MIN_SOURCE_COUNT}`、`MIN_YEAR_COUNT={MIN_YEAR_COUNT}`、`MIN_PRODUCT_COUNT={MIN_PRODUCT_COUNT}`、`MIN_OOS_FOLDS={MIN_OOS_FOLDS}`、`MIN_MEAN_PNL_LIFT={MIN_MEAN_PNL_LIFT}`。",
                "- 修改参数：无正式交易参数修改。",
                "- 删除参数：无。",
                "",
                "## 回测/归因参数",
                "",
                "- 数据区间：Stage038 opened flat-entry 样本 + Stage080 补数后的会员排名 T+1 as-of 特征。",
                "- 账户规模：不适用，本阶段无资金曲线回测。",
                "- 成本口径：不适用，本阶段无交易回放。",
                "- 样本过滤：会员排名必须 `member_rank_available=True` 才形成方向特征；OOS fold 沿用 Stage038。",
                "- 策略/归因口径：只读候选级 realized PnL/OOS/年份/品种/source 审计，不生成真实订单或资金曲线。",
                "",
                "## 结果",
                "",
                "- 期末权益：不适用。",
                "- 总收益：不适用。",
                "- 最大回撤：不适用。",
                "- Sharpe：不适用。",
                "- 总滑点：不适用。",
                "- 总交易次数：不适用。",
                "- 胜率：不适用。",
                f"- 决策：`{decision['decision']}`。",
                f"- 会员排名可用覆盖：`{decision['member_rank_available_rows']}/{decision['matrix_rows']}` = `{decision['member_rank_available_coverage_pct']:.4f}%`。",
                f"- stable candidate count：`{stable_count}`。",
                f"- 最佳候选：`{best.get('condition', '')}`。",
                "",
                "## 输出文件",
                "",
                f"- report：`{REPORT_PATH}`",
                f"- summary：`{SUMMARY_PATH}`",
                f"- fold_detail：`{FOLD_DETAIL_PATH}`",
                f"- year_detail：`{YEAR_DETAIL_PATH}`",
                f"- product_detail：`{PRODUCT_DETAIL_PATH}`",
                f"- prepared_matrix：`{PREPARED_MATRIX_PATH}`",
                f"- decision：`{DECISION_PATH}`",
                f"- chart：`{CHART_PATH}`",
                "",
                "## 候选摘要",
                "",
                _md_table(
                    summary[
                        [
                            "condition",
                            "member_rank_signal_candidate",
                            "count",
                            "total_pnl",
                            "mean_pnl_lift_vs_base",
                            "oos_positive_fold_count",
                            "oos_test_fold_count",
                            "oos_min_fold_pnl",
                            "worst_year_pnl",
                            "failure_reasons",
                        ]
                    ],
                    max_rows=20,
                ),
                "",
                "## 结论",
                "",
                f"- 本阶段结论：`{decision['decision']}`。",
                "- 是否进入下一步：只有 stable candidate 存在时，才允许冻结一个候选进入 Stage082 proxy；本阶段不能直接上线或改真实引擎。",
                "- 下一步：若有候选，做固定 `+25%` 或更保守非挤占 proxy；若无候选，关闭会员排名交易化方向。",
                "",
                "## 过拟合反思",
                "",
                "- 运行前判断：否；只读审计预声明会员排名方向特征，不根据结果调阈值。",
                "- 运行后判断：若继续围绕失败条件改符号、分位、年份、品种、方向或 topN，就是过拟合。",
                "- 原因：会员排名信号必须能穿越 source/year/product/fold，而不是解释单段左尾。",
                "",
                "## 继续价值反思",
                "",
                "- 运行前判断：有；Stage080 已修复左尾覆盖。",
                "- 运行后判断：取决于 stable candidate；即便存在也只是进入 proxy 验真。",
                "- 原因：覆盖只是资格，真正价值要看 OOS 与组合路径。",
                "",
                "## 合入建议",
                "",
                "- 是否更新本线 `LINE.md`：是，记录 Stage081 结论和下一步边界。",
                "- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage081。",
                "- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 重要摘要，不改 `memory.md`。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    raw_matrix = _read_csv(STAGE080_JOINED_FEATURES_PATH)
    fold_summary = _read_csv(STAGE038_FOLD_SUMMARY_PATH)
    matrix = prepare_member_rank_matrix(raw_matrix, fold_summary)
    specs = member_rank_condition_specs(matrix)
    summary = member_rank_condition_summary(matrix, specs)
    fold_detail = _condition_fold_detail(matrix, specs)
    year_detail = _condition_year_detail(matrix, specs)
    product_detail = _condition_product_detail(matrix, specs)
    available_rows = int(_to_bool(matrix["member_rank_available"], index=matrix.index).sum())
    decision = decision_from_member_rank_summary(summary, matrix_rows=len(matrix), available_rows=available_rows)
    decision["source_hashes"] = {
        "stage080_joined_features_sha256": _sha256_file(STAGE080_JOINED_FEATURES_PATH),
        "stage080_combined_raw_sha256": _sha256_file(STAGE080_COMBINED_RAW_PATH),
        "stage080_combined_features_sha256": _sha256_file(STAGE080_COMBINED_FEATURES_PATH),
    }
    decision["external_research_sources"] = EXTERNAL_RESEARCH_LINKS

    matrix.to_csv(PREPARED_MATRIX_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    fold_detail.to_csv(FOLD_DETAIL_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    product_detail.to_csv(PRODUCT_DETAIL_PATH, index=False, encoding="utf-8-sig")
    _plot_candidate_chart(summary)
    _write_report(decision, summary, fold_detail)
    stage_path = _write_stage_record(decision, summary)
    decision["stage_record_path"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
