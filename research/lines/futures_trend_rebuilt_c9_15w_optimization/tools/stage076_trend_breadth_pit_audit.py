from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stage038_candidate_pit_feature_matrix_audit import (
    ConditionSpec,
    build_purged_time_splits,
    summarize_condition_oos,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage076"
MODEL_TAG = "stage076_trend_breadth_pit_audit_v1"
STAGE_SLUG = "stage076_trend_breadth_pit_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage076_trend_breadth_pit_audit"

MAX_FEATURE_AGE_DAYS = 7
N_SPLITS = 4
EMBARGO_DAYS = 20

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
REPO_ROOT = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE038_FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"

STAGE017_OUTPUT_DIR = LINE_DIR / "outputs" / "stage017_external_regime_volatility_attribution"
STAGE017_PREFIX = "rebuilt_c9_stage017_external_regime_volatility_attribution"
STAGE017_TAG = "stage017_external_regime_volatility_attribution_v1"
STAGE017_MARKET_DAILY_PATH = STAGE017_OUTPUT_DIR / f"{STAGE017_PREFIX}_market_daily_summary_{STAGE017_TAG}.csv"

JOINED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_feature_matrix_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_oos_summary_{MODEL_TAG}.csv"
FEATURE_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_coverage_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
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


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def attach_pit_breadth_features(
    entries: pd.DataFrame,
    market_daily: pd.DataFrame,
    *,
    max_feature_age_days: int = MAX_FEATURE_AGE_DAYS,
) -> pd.DataFrame:
    """Attach latest market breadth row visible at entry time.

    Stage017 market daily rows are built from that day's completed bars, so a
    row dated D is only visible from D+1. This keeps the audit point-in-time and
    intentionally leaves later entries unmatched when the source stops early.
    """
    result = entries.copy()
    if result.empty:
        return result
    result["_stage076_row_id"] = np.arange(len(result))
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()

    feature_columns = {
        "trend_breadth_feature_date": pd.NaT,
        "trend_breadth_asof_date": pd.NaT,
        "trend_breadth_feature_age_days": np.nan,
        "trend_breadth_share": np.nan,
        "trend_breadth_product_count": np.nan,
        "trend_breadth_dispersion": np.nan,
        "trend_breadth_median_ret60": np.nan,
        "trend_breadth_median_eff60": np.nan,
        "trend_breadth_median_vol60": np.nan,
        "trend_breadth_bucket": "",
        "trend_breadth_joint_regime": "",
        "trend_breadth_vol60_bucket": "",
        "trend_breadth_eff60_bucket": "",
        "trend_breadth_close_extreme_bucket": "",
    }
    for column, default in feature_columns.items():
        if column not in result.columns:
            result[column] = default
    result["trend_breadth_matched"] = False

    if market_daily.empty:
        return result.drop(columns=["_stage076_row_id"])

    market = market_daily.copy()
    market["trend_breadth_feature_date"] = pd.to_datetime(market["date"], errors="coerce").dt.normalize()
    market["trend_breadth_asof_date"] = market["trend_breadth_feature_date"] + pd.Timedelta(days=1)
    rename_map = {
        "ma20_over_ma60_share_60d": "trend_breadth_share",
        "product_count": "trend_breadth_product_count",
        "cross_section_ret60_dispersion": "trend_breadth_dispersion",
        "median_ret_60d": "trend_breadth_median_ret60",
        "median_trend_efficiency_60d": "trend_breadth_median_eff60",
        "median_realized_vol_60d": "trend_breadth_median_vol60",
        "trend_breadth_bucket": "trend_breadth_bucket",
        "joint_regime": "trend_breadth_joint_regime",
        "vol60_bucket": "trend_breadth_vol60_bucket",
        "trend_eff60_bucket": "trend_breadth_eff60_bucket",
        "close_extreme_bucket": "trend_breadth_close_extreme_bucket",
    }
    available = [
        "trend_breadth_feature_date",
        "trend_breadth_asof_date",
        *[column for column in rename_map if column in market.columns],
    ]
    market = (
        market[available]
        .rename(columns=rename_map)
        .dropna(subset=["trend_breadth_asof_date"])
        .sort_values("trend_breadth_asof_date")
    )
    if market.empty:
        return result.drop(columns=["_stage076_row_id"])

    merged = pd.merge_asof(
        result.sort_values("entry_date"),
        market,
        left_on="entry_date",
        right_on="trend_breadth_asof_date",
        direction="backward",
        tolerance=pd.Timedelta(days=max_feature_age_days),
        suffixes=("", "_stage076_feature"),
    )
    for column in feature_columns:
        feature_column = f"{column}_stage076_feature"
        if feature_column in merged.columns:
            merged[column] = merged[feature_column]
            merged = merged.drop(columns=[feature_column])

    age = (
        pd.to_datetime(merged["entry_date"], errors="coerce").dt.normalize()
        - pd.to_datetime(merged["trend_breadth_asof_date"], errors="coerce").dt.normalize()
    ).dt.days
    merged["trend_breadth_feature_age_days"] = age
    matched = age.notna() & age.ge(0) & age.le(max_feature_age_days)
    merged["trend_breadth_matched"] = matched.fillna(False).astype(bool)

    stale = ~merged["trend_breadth_matched"]
    clear_columns = [
        "trend_breadth_feature_date",
        "trend_breadth_asof_date",
        "trend_breadth_feature_age_days",
        "trend_breadth_share",
        "trend_breadth_product_count",
        "trend_breadth_dispersion",
        "trend_breadth_median_ret60",
        "trend_breadth_median_eff60",
        "trend_breadth_median_vol60",
    ]
    for column in clear_columns:
        merged.loc[stale, column] = pd.NaT if column.endswith("_date") else np.nan
    text_columns = [
        "trend_breadth_bucket",
        "trend_breadth_joint_regime",
        "trend_breadth_vol60_bucket",
        "trend_breadth_eff60_bucket",
        "trend_breadth_close_extreme_bucket",
    ]
    for column in text_columns:
        merged[column] = merged[column].fillna("").astype(str)
        merged.loc[stale, column] = ""
    return merged.sort_values("_stage076_row_id").drop(columns=["_stage076_row_id"]).reset_index(drop=True)


def build_trend_breadth_condition_specs(matrix: pd.DataFrame) -> list[ConditionSpec]:
    matched = _to_bool(matrix.get("trend_breadth_matched", False), index=matrix.index)
    bucket = matrix.get("trend_breadth_bucket", pd.Series("", index=matrix.index)).fillna("").astype(str)
    regime = matrix.get("trend_breadth_joint_regime", pd.Series("", index=matrix.index)).fillna("").astype(str)
    ai_top8 = _to_bool(matrix.get("full_market_ai_top8", False), index=matrix.index)
    account_injured = _to_bool(matrix.get("account_injured", False), index=matrix.index)
    breadth_mid_or_high = matched & bucket.isin(["breadth_mid", "breadth_high"])
    breadth_high = matched & bucket.eq("breadth_high")
    broad_trend = matched & regime.eq("broad_trend")
    narrow_or_chop = matched & (bucket.eq("breadth_low") | regime.isin(["narrow_chop", "quiet_low_eff"]))
    high_vol_low_eff = matched & regime.eq("high_vol_low_eff")

    return [
        ConditionSpec(
            "breadth_matched",
            "T+1 可见市场广度特征命中；只作覆盖基准",
            "breadth_coverage",
            False,
            matched,
        ),
        ConditionSpec(
            "breadth_mid_or_high",
            "市场 MA20>MA60 参与度为中/高",
            "trend_breadth",
            True,
            breadth_mid_or_high,
        ),
        ConditionSpec(
            "breadth_high",
            "市场 MA20>MA60 参与度高",
            "trend_breadth",
            True,
            breadth_high,
        ),
        ConditionSpec(
            "broad_trend_regime",
            "Stage017 joint regime 为 broad_trend",
            "trend_breadth",
            True,
            broad_trend,
        ),
        ConditionSpec(
            "breadth_low_or_narrow_chop",
            "市场广度低或 narrow/quiet chop",
            "trend_breadth_risk",
            True,
            narrow_or_chop,
        ),
        ConditionSpec(
            "high_vol_low_eff_breadth_context",
            "高波动低趋势效率环境",
            "trend_breadth_risk",
            True,
            high_vol_low_eff,
        ),
        ConditionSpec(
            "full_market_ai_top8_and_breadth_mid_or_high",
            "full-market AI top8 且市场广度中/高",
            "ai_breadth",
            True,
            ai_top8 & breadth_mid_or_high,
        ),
        ConditionSpec(
            "full_market_ai_top8_and_breadth_high",
            "full-market AI top8 且市场广度高",
            "ai_breadth",
            True,
            ai_top8 & breadth_high,
        ),
        ConditionSpec(
            "full_market_ai_top8_and_broad_trend",
            "full-market AI top8 且整体 broad_trend",
            "ai_breadth",
            True,
            ai_top8 & broad_trend,
        ),
        ConditionSpec(
            "account_injured_and_breadth_mid_or_high",
            "账户受伤但市场广度中/高",
            "account_breadth",
            True,
            account_injured & breadth_mid_or_high,
        ),
        ConditionSpec(
            "account_injured_and_ai_top8_and_breadth_mid_or_high",
            "账户受伤 + full-market AI top8 + 市场广度中/高",
            "ai_account_breadth",
            True,
            account_injured & ai_top8 & breadth_mid_or_high,
        ),
    ]


def add_breadth_condition_robustness(
    matrix: pd.DataFrame,
    condition_summary: pd.DataFrame,
    conditions: list[ConditionSpec],
    *,
    max_top10_positive_pnl_share_pct: float = 55.0,
) -> pd.DataFrame:
    result = condition_summary.copy()
    if result.empty:
        return result
    condition_by_name = {condition.name: condition for condition in conditions}
    pnl_all = pd.to_numeric(matrix.get("realized_pnl"), errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for _, row in result.iterrows():
        condition = condition_by_name.get(str(row["condition"]))
        if condition is None:
            rows.append(
                {
                    "condition": row["condition"],
                    "min_year_pnl": np.nan,
                    "negative_year_count": np.nan,
                    "top10_positive_pnl_share_pct": np.nan,
                    "top_product_positive_pnl_share_pct": np.nan,
                    "stage076_robust_candidate": False,
                }
            )
            continue
        mask = condition.mask.reindex(matrix.index).fillna(False).astype(bool)
        subset = matrix.loc[mask].copy()
        pnl = pnl_all.loc[mask]
        if subset.empty:
            min_year_pnl = np.nan
            negative_year_count = 0
            top10_share = np.nan
            top_product_share = np.nan
        else:
            year_pnl = pnl.groupby(subset.get("entry_year")).sum()
            min_year_pnl = float(year_pnl.min()) if not year_pnl.empty else np.nan
            negative_year_count = int((year_pnl < 0).sum()) if not year_pnl.empty else 0
            positive = pnl[pnl > 0].sort_values(ascending=False)
            positive_sum = float(positive.sum())
            top10_share = float(positive.head(10).sum() / positive_sum * 100.0) if positive_sum else np.nan
            if "product_vt_symbol" in subset.columns and positive_sum:
                product_positive = (
                    pd.DataFrame({"product_vt_symbol": subset["product_vt_symbol"], "pnl": pnl})
                    .query("pnl > 0")
                    .groupby("product_vt_symbol")["pnl"]
                    .sum()
                    .sort_values(ascending=False)
                )
                top_product_share = float(product_positive.iloc[0] / positive_sum * 100.0) if len(product_positive) else np.nan
            else:
                top_product_share = np.nan
        stage076_robust = (
            bool(row.get("stable_oos_candidate", False))
            and pd.notna(min_year_pnl)
            and float(min_year_pnl) > 0.0
            and negative_year_count == 0
            and pd.notna(top10_share)
            and float(top10_share) <= max_top10_positive_pnl_share_pct
        )
        rows.append(
            {
                "condition": row["condition"],
                "min_year_pnl": min_year_pnl,
                "negative_year_count": negative_year_count,
                "top10_positive_pnl_share_pct": top10_share,
                "top_product_positive_pnl_share_pct": top_product_share,
                "stage076_robust_candidate": bool(stage076_robust),
            }
        )
    robust = pd.DataFrame(rows)
    return result.merge(robust, on="condition", how="left")


def summarize_breadth_feature_coverage(
    matrix: pd.DataFrame,
    *,
    market_min_date: pd.Timestamp | pd.NaT,
    market_max_date: pd.Timestamp | pd.NaT,
) -> dict[str, Any]:
    matched = _to_bool(matrix.get("trend_breadth_matched", False), index=matrix.index)
    entry_dates = pd.to_datetime(matrix.get("entry_date"), errors="coerce").dt.normalize()
    ages = pd.to_numeric(matrix.get("trend_breadth_feature_age_days"), errors="coerce")
    return {
        "entry_count": int(len(matrix)),
        "matched_entry_count": int(matched.sum()),
        "matched_entry_pct": float(matched.mean() * 100.0) if len(matrix) else 0.0,
        "min_entry_date": entry_dates.min().date().isoformat() if entry_dates.notna().any() else "",
        "max_entry_date": entry_dates.max().date().isoformat() if entry_dates.notna().any() else "",
        "market_min_date": pd.Timestamp(market_min_date).date().isoformat() if pd.notna(market_min_date) else "",
        "market_max_date": pd.Timestamp(market_max_date).date().isoformat() if pd.notna(market_max_date) else "",
        "max_feature_age_days": int(ages.max()) if ages.notna().any() else None,
        "median_feature_age_days": float(ages.median()) if ages.notna().any() else None,
        "has_recent_market_gap": bool(
            pd.notna(market_max_date) and entry_dates.notna().any() and pd.Timestamp(market_max_date) < entry_dates.max()
        ),
    }


def _bucket_summary(matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pnl_all = pd.to_numeric(matrix.get("realized_pnl"), errors="coerce").fillna(0.0)
    base_mean = float(pnl_all.mean()) if len(matrix) else 0.0
    for feature in ["trend_breadth_bucket", "trend_breadth_joint_regime", "trend_breadth_vol60_bucket"]:
        if feature not in matrix.columns:
            continue
        for value, group in matrix.groupby(feature, dropna=False):
            if not str(value):
                continue
            pnl = pd.to_numeric(group.get("realized_pnl"), errors="coerce").fillna(0.0)
            rows.append(
                {
                    "feature": feature,
                    "feature_value": str(value),
                    "count": int(len(group)),
                    "source_count": int(group["requested_start_month"].nunique())
                    if "requested_start_month" in group.columns
                    else 0,
                    "year_count": int(group["entry_year"].nunique()) if "entry_year" in group.columns else 0,
                    "total_pnl": float(pnl.sum()),
                    "mean_pnl": float(pnl.mean()) if len(group) else 0.0,
                    "mean_pnl_lift_vs_base": float(pnl.mean() / base_mean) if base_mean and len(group) else np.nan,
                    "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(group) else 0.0,
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["mean_pnl_lift_vs_base", "total_pnl"], ascending=[False, False]).reset_index(drop=True)


def _decision(
    joined: pd.DataFrame,
    condition_summary: pd.DataFrame,
    coverage: dict[str, Any],
    bucket_summary: pd.DataFrame,
) -> dict[str, Any]:
    raw_stable = condition_summary[condition_summary["stable_oos_candidate"].astype(bool)].copy()
    robust = condition_summary[condition_summary.get("stage076_robust_candidate", False).astype(bool)].copy()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage076_trend_breadth_keep_readonly_no_trade_rule",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_feature_matrix": str(STAGE038_FEATURE_MATRIX_PATH),
        "source_market_daily": str(STAGE017_MARKET_DAILY_PATH),
        "max_feature_age_days": MAX_FEATURE_AGE_DAYS,
        "entry_count": int(len(joined)),
        "raw_stable_condition_count": int(len(raw_stable)),
        "raw_stable_conditions": raw_stable["condition"].astype(str).tolist(),
        "stable_condition_count": int(len(robust)),
        "stable_conditions": robust["condition"].astype(str).tolist(),
        "coverage": coverage,
        "top_bucket": bucket_summary.head(1).to_dict("records")[0] if not bucket_summary.empty else {},
        "overfit_reflection_before": "否；本阶段先按外部趋势跟随分散化逻辑审计整体广度，不按最差窗口、品种、方向、月份或手数调参。",
        "overfit_reflection_after": "低但未消除；如果 stable 条件存在，也只能作为下一阶段冻结 proxy 的资格，不能直接按本阶段结果上线。",
        "continue_value_before": "有价值；Stage074/075 证明账户冷启动降风险会伤右尾，广度/分散度是更贴近趋势策略本质的 PIT 信息。",
        "continue_value_after": "取决于 stable 条件和覆盖缺口；若无稳定候选或覆盖缺口过大，应转向补齐 market daily 到 2026-06 或寻找新外生源。",
        "next_stage": "若 stable condition 非空，冻结一个条件做 add-risk/eligibility proxy；否则先补齐 market daily 或转新 PIT 信息源。",
    }


def _write_report(
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    coverage_frame: pd.DataFrame,
    bucket_summary: pd.DataFrame,
) -> None:
    lines = [
        f"# {STAGE} 趋势广度/分散度 PIT 只读审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- stable OOS condition count：`{decision['stable_condition_count']}`。",
        f"- stable conditions：`{', '.join(decision['stable_conditions']) if decision['stable_conditions'] else '无'}`。",
        f"- raw stable OOS conditions：`{', '.join(decision['raw_stable_conditions']) if decision['raw_stable_conditions'] else '无'}`。",
        "- 本阶段只审计候选级信息含量，不改 C9、不接 CTP、不作为实盘规则。",
        "",
        "## 覆盖率",
        "",
        _md_table(coverage_frame),
        "",
        "## 条件 OOS 摘要",
        "",
        _md_table(
            condition_summary[
                [
                    "condition",
                    "candidate_eligible",
                    "count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "win_rate_lift_pp",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "stable_oos_candidate",
                    "min_year_pnl",
                    "negative_year_count",
                    "top10_positive_pnl_share_pct",
                    "stage076_robust_candidate",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## 分桶摘要",
        "",
        _md_table(bucket_summary, max_rows=20),
        "",
        "## 输出",
        "",
        f"- joined_feature_matrix：`{JOINED_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- feature_coverage：`{FEATURE_COVERAGE_PATH}`",
        f"- bucket_summary：`{BUCKET_SUMMARY_PATH}`",
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


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage076_trend_breadth_pit_audit.md"
    top_conditions = condition_summary.head(12).copy()
    lines = [
        f"# {STAGE} trend breadth PIT audit",
        "",
        f"- 时间：{decision['generated_at']} CST",
        f"- line_id：`{LINE_ID}`",
        "- 类型：只读候选级 PIT 审计，不改线上、不改实盘执行。",
        "- 外部调研：趋势跟随长期有效性来自跨市场/跨资产分散和 time-series momentum，开源 `pysystemtrade` 也以多市场系统化组合为核心；因此本阶段采纳“整体趋势广度/参与度”作为低自由度候选信息，不采纳单品种/方向/窗口补丁。",
        "",
        "## 版本变更",
        "",
        "- 新增参数：`MAX_FEATURE_AGE_DAYS=7`，仅用于 T+1 market breadth 特征过期控制。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "- 新增回测结果：无真实回测；新增候选级 OOS 条件审计和覆盖率审计。",
        "- 修改回测结果：无。",
        "- 删除回测结果：无。",
        "",
        "## 结果",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- entry_count：`{decision['entry_count']}`。",
        f"- matched_entry_pct：`{decision['coverage']['matched_entry_pct']:.4f}%`。",
        f"- market date range：`{decision['coverage']['market_min_date']} -> {decision['coverage']['market_max_date']}`。",
        f"- entry date range：`{decision['coverage']['min_entry_date']} -> {decision['coverage']['max_entry_date']}`。",
        f"- has_recent_market_gap：`{decision['coverage']['has_recent_market_gap']}`。",
        f"- stable OOS condition count：`{decision['stable_condition_count']}`。",
        f"- stable conditions：`{', '.join(decision['stable_conditions']) if decision['stable_conditions'] else '无'}`。",
        f"- raw stable OOS conditions：`{', '.join(decision['raw_stable_conditions']) if decision['raw_stable_conditions'] else '无'}`。",
        "",
        "## 条件摘要",
        "",
        _md_table(
            top_conditions[
                [
                    "condition",
                    "count",
                    "total_pnl",
                    "mean_pnl_lift_vs_base",
                    "oos_positive_fold_count",
                    "oos_test_fold_count",
                    "oos_min_fold_pnl",
                    "stable_oos_candidate",
                    "min_year_pnl",
                    "negative_year_count",
                    "top10_positive_pnl_share_pct",
                    "stage076_robust_candidate",
                ]
            ],
            max_rows=12,
        ),
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
    entries = _read_csv(STAGE038_FEATURE_MATRIX_PATH)
    market_daily = _read_csv(STAGE017_MARKET_DAILY_PATH)
    market_dates = pd.to_datetime(market_daily.get("date"), errors="coerce").dt.normalize()
    joined = attach_pit_breadth_features(entries, market_daily)
    splits = build_purged_time_splits(joined, date_column="entry_date", n_splits=N_SPLITS, embargo_days=EMBARGO_DAYS)
    conditions = build_trend_breadth_condition_specs(joined)
    condition_summary = summarize_condition_oos(joined, splits, conditions)
    condition_summary = add_breadth_condition_robustness(joined, condition_summary, conditions)
    coverage = summarize_breadth_feature_coverage(
        joined,
        market_min_date=market_dates.min() if market_dates.notna().any() else pd.NaT,
        market_max_date=market_dates.max() if market_dates.notna().any() else pd.NaT,
    )
    coverage_frame = pd.DataFrame([coverage])
    bucket_summary = _bucket_summary(joined)
    decision = _decision(joined, condition_summary, coverage, bucket_summary)
    _write_report(decision, condition_summary, coverage_frame, bucket_summary)
    stage_record = _write_stage_record(decision, condition_summary)
    decision["stage_record_path"] = str(stage_record)

    joined.to_csv(JOINED_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    coverage_frame.to_csv(FEATURE_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    decision = run()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
