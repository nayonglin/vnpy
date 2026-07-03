from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage077"
MODEL_TAG = "stage077_jd_independent_candidate_audit_v1"
STAGE_SLUG = "stage077_jd_independent_candidate_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage077_jd_independent_candidate_audit"

PRODUCT_VT_SYMBOL = "jd.DCE"
MIN_COUNT = 6
MIN_YEARS = 3
MIN_TOTAL_PNL = 50000.0
N_SPLITS = 4

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE021_OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"
STAGE021_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"
STAGE021_TAG = "stage021_full_market_consensus_jd_proxy_v1"
FULL_MARKET_PREDICTIONS_PATH = (
    STAGE021_OUTPUT_DIR / f"{STAGE021_PREFIX}_full_market_predictions_ranked_{STAGE021_TAG}.csv"
)

JD_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_jd_monthly_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class JdCondition:
    name: str
    description: str
    eligible: bool
    mask: pd.Series


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


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _to_bool(values: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.copy()
    else:
        series = pd.Series(values, index=index)
    if series.empty:
        return series.astype(bool)
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0).ne(0)
    text = series.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def _product_key(values: pd.Series | Any) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.fillna("").astype(str).str.strip().str.lower()
    return pd.Series(values).fillna("").astype(str).str.strip().str.lower()


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def extract_product_monthly_predictions(
    predictions: pd.DataFrame,
    *,
    product_vt_symbol: str = PRODUCT_VT_SYMBOL,
) -> pd.DataFrame:
    required = {"eval_date", "product_vt_symbol"}
    if not required.issubset(predictions.columns):
        missing = sorted(required - set(predictions.columns))
        raise KeyError(f"missing required columns: {missing}")
    frame = predictions.copy()
    frame["product_key"] = _product_key(frame["product_vt_symbol"])
    target_key = product_vt_symbol.strip().lower()
    frame = frame[frame["product_key"].eq(target_key)].copy()
    if frame.empty:
        return frame.reset_index(drop=True)
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize()
    frame["eval_year"] = frame["eval_date"].dt.year
    for column in [
        "ai_rank_desc",
        "simple_rank_desc",
        "future_net_pnl_60d",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["jd_ai_top8"] = _to_bool(frame.get("stage021_ai_top8", False), index=frame.index)
    frame["jd_simple_top8"] = _to_bool(frame.get("stage021_simple_top8", False), index=frame.index)
    frame["jd_consensus_top8"] = _to_bool(frame.get("stage021_consensus_top8", False), index=frame.index)
    frame["jd_ai_or_simple_top8"] = frame["jd_ai_top8"] | frame["jd_simple_top8"]
    frame["jd_ai_only_top8"] = frame["jd_ai_top8"] & ~frame["jd_simple_top8"]
    frame["jd_simple_only_top8"] = frame["jd_simple_top8"] & ~frame["jd_ai_top8"]
    frame["future_net_pnl_60d"] = pd.to_numeric(frame.get("future_net_pnl_60d"), errors="coerce").fillna(0.0)
    return frame.sort_values("eval_date").reset_index(drop=True)


def build_jd_selector_conditions(frame: pd.DataFrame) -> list[JdCondition]:
    index = frame.index
    ai_top8 = _to_bool(frame.get("jd_ai_top8", False), index=index)
    simple_top8 = _to_bool(frame.get("jd_simple_top8", False), index=index)
    consensus = _to_bool(frame.get("jd_consensus_top8", False), index=index)
    ai_or_simple = ai_top8 | simple_top8
    return [
        JdCondition("all_jd_months", "jd 全部 full-market 月度预测；只作覆盖基准", False, pd.Series(True, index=index)),
        JdCondition("jd_ai_top8_independent", "jd 进入 full-market AI top8；仅作为独立非挤占候选", True, ai_top8),
        JdCondition(
            "jd_simple_top8_independent",
            "jd 进入 simple trend top8；仅作为独立非挤占候选",
            True,
            simple_top8,
        ),
        JdCondition(
            "jd_consensus_top8_independent",
            "jd 同时进入 full-market AI top8 与 simple top8；仅作为独立非挤占候选",
            True,
            consensus,
        ),
        JdCondition(
            "jd_ai_or_simple_top8_independent",
            "jd 进入 AI top8 或 simple top8；仅作宽松独立观察",
            True,
            ai_or_simple,
        ),
    ]


def _fold_masks(frame: pd.DataFrame, n_splits: int = N_SPLITS) -> list[pd.Series]:
    dates = list(pd.to_datetime(frame["eval_date"], errors="coerce").dropna().sort_values())
    if not dates:
        return []
    chunks = np.array_split(np.asarray(dates, dtype="datetime64[ns]"), n_splits)
    masks: list[pd.Series] = []
    eval_dates = pd.to_datetime(frame["eval_date"], errors="coerce")
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        masks.append(eval_dates.between(chunk.min(), chunk.max(), inclusive="both"))
    return masks


def summarize_jd_conditions(
    frame: pd.DataFrame,
    conditions: list[JdCondition],
    *,
    min_count: int = MIN_COUNT,
    min_years: int = MIN_YEARS,
    min_total_pnl: float = MIN_TOTAL_PNL,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    pnl_all = pd.to_numeric(frame["future_net_pnl_60d"], errors="coerce").fillna(0.0)
    folds = _fold_masks(frame)
    rows: list[dict[str, Any]] = []
    for condition in conditions:
        mask = condition.mask.reindex(frame.index).fillna(False).astype(bool)
        subset = frame.loc[mask].copy()
        pnl = pnl_all.loc[mask]
        year_pnl = pnl.groupby(subset["eval_year"]).sum() if not subset.empty else pd.Series(dtype="float64")
        fold_pnls = [float(pnl_all.loc[fold.reindex(frame.index).fillna(False) & mask].sum()) for fold in folds]
        active_fold_pnls = [value for value in fold_pnls if abs(value) > 1e-12]
        positive_fold_count = sum(1 for value in active_fold_pnls if value > 0)
        positive = pnl[pnl > 0].sort_values(ascending=False)
        positive_sum = float(positive.sum())
        top5_positive_share = float(positive.head(5).sum() / positive_sum * 100.0) if positive_sum else np.nan
        negative_year_count = int((year_pnl < 0).sum()) if not year_pnl.empty else 0
        total_pnl = float(pnl.sum()) if len(subset) else 0.0
        candidate = (
            condition.eligible
            and len(subset) >= min_count
            and subset["eval_year"].nunique() >= min_years
            and total_pnl >= min_total_pnl
            and negative_year_count == 0
            and len(active_fold_pnls) >= 3
            and positive_fold_count == len(active_fold_pnls)
        )
        rows.append(
            {
                "condition": condition.name,
                "description": condition.description,
                "eligible_independent": bool(condition.eligible),
                "count": int(len(subset)),
                "coverage_pct": float(len(subset) / len(frame) * 100.0) if len(frame) else 0.0,
                "year_count": int(subset["eval_year"].nunique()) if not subset.empty else 0,
                "total_future_net_pnl_60d": total_pnl,
                "mean_future_net_pnl_60d": float(pnl.mean()) if len(subset) else 0.0,
                "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(subset) else 0.0,
                "min_year_pnl": float(year_pnl.min()) if not year_pnl.empty else np.nan,
                "negative_year_count": negative_year_count,
                "oos_fold_count": int(len(active_fold_pnls)),
                "oos_positive_fold_count": int(positive_fold_count),
                "oos_min_fold_pnl": float(min(active_fold_pnls)) if active_fold_pnls else np.nan,
                "top5_positive_pnl_share_pct": top5_positive_share,
                "stage077_independent_candidate": bool(candidate),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["stage077_independent_candidate", "eligible_independent", "total_future_net_pnl_60d", "count"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def _year_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    return (
        frame.groupby("eval_year")
        .agg(
            month_count=("eval_date", "count"),
            future_net_pnl_60d=("future_net_pnl_60d", "sum"),
            ai_top8_months=("jd_ai_top8", "sum"),
            simple_top8_months=("jd_simple_top8", "sum"),
            consensus_top8_months=("jd_consensus_top8", "sum"),
        )
        .reset_index()
    )


def _decision(jd: pd.DataFrame, condition_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = condition_summary[condition_summary["stage077_independent_candidate"].astype(bool)].copy()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage077_jd_not_independent_candidate_keep_observe",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_predictions": str(FULL_MARKET_PREDICTIONS_PATH),
        "product_vt_symbol": PRODUCT_VT_SYMBOL,
        "month_count": int(len(jd)),
        "eval_date_min": jd["eval_date"].min().date().isoformat() if not jd.empty else "",
        "eval_date_max": jd["eval_date"].max().date().isoformat() if not jd.empty else "",
        "total_future_net_pnl_60d": float(jd["future_net_pnl_60d"].sum()) if not jd.empty else 0.0,
        "candidate_count": int(len(candidates)),
        "candidate_conditions": candidates["condition"].astype(str).tolist(),
        "overfit_reflection_before": "否；本阶段只审计 jd 独立非挤占资格，不把 jd 塞入共享 AI rerank，也不扫 sleeve 大小、月份、方向或 TopN。",
        "overfit_reflection_after": "否；若没有稳定候选，继续调 jd AI rank、simple rank、年份或风险预算就是过拟合。",
        "continue_value_before": "有价值；用户目标明确要求基础池加鸡蛋，但历史反证要求先证明 jd 独立材料性。",
        "continue_value_after": "有限；若 jd 仍无独立候选，应保留数据资产和 forward watch，转更强 PIT 信息源或非鸡蛋主线。",
        "next_stage": "若 candidate_conditions 为空，停止 jd 共享/独立历史救参；只允许 forward watch 或新特征证明后再给小独立预算。",
    }


def _write_report(decision: dict[str, Any], condition_summary: pd.DataFrame, year_summary: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} jd.DCE 独立非挤占候选审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- candidate count：`{decision['candidate_count']}`。",
        f"- candidate conditions：`{', '.join(decision['candidate_conditions']) if decision['candidate_conditions'] else '无'}`。",
        "- 本阶段不改 C9、不改共享 AI 池、不接 CTP、不生成交易候选。",
        "",
        "## 条件摘要",
        "",
        _md_table(condition_summary, max_rows=20),
        "",
        "## 年度摘要",
        "",
        _md_table(year_summary, max_rows=20),
        "",
        "## 输出",
        "",
        f"- jd_matrix：`{JD_MATRIX_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- year_summary：`{YEAR_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame, year_summary: pd.DataFrame) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage077_jd_independent_candidate_audit.md"
    lines = [
        "# Stage077 jd.DCE independent candidate audit",
        "",
        f"- 时间：{decision['generated_at']} CST",
        f"- line_id：`{LINE_ID}`",
        "- 类型：只读资格审计，不改线上、不改共享 AI 池、不接实盘。",
        "- 外部调研：趋势跟随鼓励增加可交易市场和分散化，但新增品种应先看资本承载、独立材料性和点时 selector；本阶段采纳“jd 只能先独立非挤占审计”的方向，不采纳共享 AI rerank。",
        "",
        "## 版本变更",
        "",
        "- 新增参数：`MIN_COUNT=6`、`MIN_YEARS=3`、`MIN_TOTAL_PNL=50000`，仅用于 jd 独立候选资格门。",
        "- 修改参数：无正式交易参数修改。",
        "- 删除参数：无。",
        "- 新增回测结果：无真实资金曲线回测；新增 jd full-market 月度选择器资格审计。",
        "- 修改回测结果：无。",
        "- 删除回测结果：无。",
        "",
        "## 结果",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- jd month count：`{decision['month_count']}`，日期 `{decision['eval_date_min']} -> {decision['eval_date_max']}`。",
        f"- jd 全部 60d future PnL 合计：`{decision['total_future_net_pnl_60d']:.4f}`。",
        f"- independent candidate count：`{decision['candidate_count']}`。",
        f"- candidate conditions：`{', '.join(decision['candidate_conditions']) if decision['candidate_conditions'] else '无'}`。",
        "",
        "## 条件摘要",
        "",
        _md_table(condition_summary, max_rows=12),
        "",
        "## 年度摘要",
        "",
        _md_table(year_summary, max_rows=12),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
        "",
        "## 后续规划和 TODO",
        "",
        f"- 下一步：`{decision['next_stage']}`。",
    ]
    stage_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions = _read_csv(FULL_MARKET_PREDICTIONS_PATH)
    jd = extract_product_monthly_predictions(predictions)
    conditions = build_jd_selector_conditions(jd)
    condition_summary = summarize_jd_conditions(jd, conditions)
    year_summary = _year_summary(jd)
    decision = _decision(jd, condition_summary)
    _write_report(decision, condition_summary, year_summary)
    stage_record = _write_stage_record(decision, condition_summary, year_summary)
    decision["stage_record_path"] = str(stage_record)

    jd.to_csv(JD_MATRIX_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
