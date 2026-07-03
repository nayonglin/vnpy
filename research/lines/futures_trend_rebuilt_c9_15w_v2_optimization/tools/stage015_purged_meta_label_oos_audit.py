from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage015"
MODEL_TAG = "stage015_purged_meta_label_oos_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage015_purged_meta_label_oos_audit"
EMBARGO_DAYS = 20
MIN_TRAIN_ROWS = 200

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_meta_label_entry_quality_audit as s009_quality


OUTPUT_DIR = LINE_DIR / "outputs" / "stage015_purged_meta_label_oos_audit"
STAGE009_OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_meta_label_entry_quality_audit"
STAGE009_PREFIX = "rebuilt_c9_v2_stage009_meta_label_entry_quality_audit"
STAGE009_TAG = "stage009_meta_label_entry_quality_audit_v1"
STAGE009_EVENTS_PATH = STAGE009_OUTPUT_DIR / f"{STAGE009_PREFIX}_quality_events_{STAGE009_TAG}.csv.gz"

SCORED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scored_samples_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
YEAR_COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_comparison_{MODEL_TAG}.csv"
FEATURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oos_bucket_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0501_stage015_purged_meta_label_oos_audit.md"

NUMERIC_FEATURES = [
    "ai_product_pool_rank",
    "ai_product_pool_score",
    "rsi_value",
    "breakout",
    "bullish_alignment",
    "bearish_alignment",
    "portfolio_drawdown_abs_pct",
    "same_direction_correlation_max_corr",
    "same_direction_correlation_active_count",
    "active_positions_before",
    "loss_streak",
    "risk_multiplier",
    "target_risk_amount",
    "selected_volume",
    "contracts_by_risk",
    "contracts_by_margin",
    "stop_distance",
    "entry_risk_distance_pct_abs",
]
CATEGORICAL_FEATURES = [
    "product",
    "direction",
    "signal",
    "risk_mode",
    "entry_context",
    "layer_kind",
    "risk_multiplier_bucket",
    "loss_streak_bucket",
    "active_positions_bucket",
    "ai_rank_bucket",
    "rsi_bucket",
    "stop_distance_bucket",
    "recovery_bucket",
    "streak_recovery_bucket",
    "breakout_bucket",
]


@dataclass(frozen=True)
class WalkForwardSplit:
    test_year: int
    train_index: pd.Index
    test_index: pd.Index


def _json_safe(value: Any) -> Any:
    return s009_quality._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009_quality._md_table(frame, max_rows=max_rows or 30)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _actual_trade_key(frame: pd.DataFrame) -> pd.Series:
    if {"open_trade_id", "close_trade_id"}.issubset(frame.columns):
        return frame["open_trade_id"].astype(str) + "|" + frame["close_trade_id"].astype(str)
    pieces = []
    for column in ["vt_symbol", "entry_date", "exit_date", "entry_price", "exit_price", "realized_pnl"]:
        pieces.append(frame[column].astype(str) if column in frame.columns else pd.Series("", index=frame.index))
    return pieces[0].str.cat(pieces[1:], sep="|")


def prepare_model_samples(events: pd.DataFrame) -> pd.DataFrame:
    data = events.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["entry_date", "exit_date"]).copy()
    data["entry_year"] = data["entry_date"].dt.year.astype("int64")
    data["actual_trade_key"] = _actual_trade_key(data)
    data["realized_pnl"] = _numeric(data, "realized_pnl", 0.0).fillna(0.0)
    data["big_winner"] = _numeric(data, "big_winner", 0.0).fillna(0.0).gt(0).astype("int64")
    data["bad_path"] = _numeric(data, "bad_path", 0.0).fillna(0.0).gt(0).astype("int64")
    data["winner"] = data["realized_pnl"].gt(0.0).astype("int64")
    data["stage015_quality_label"] = ((data["winner"].eq(1) & data["bad_path"].eq(0)) | data["big_winner"].eq(1)).astype(
        "int64"
    )
    for column in NUMERIC_FEATURES:
        data[column] = _numeric(data, column)
    for column in CATEGORICAL_FEATURES:
        if column not in data.columns:
            data[column] = "missing"
        data[column] = data[column].astype(str).fillna("missing")
    sort_cols = ["entry_date", "actual_trade_key"]
    if "requested_start_month" in data.columns:
        sort_cols.append("requested_start_month")
    return data.sort_values(sort_cols).drop_duplicates("actual_trade_key", keep="first").reset_index(drop=True)


def build_purged_walk_forward_splits(
    samples: pd.DataFrame,
    test_years: list[int] | None = None,
    embargo_days: int = EMBARGO_DAYS,
) -> list[WalkForwardSplit]:
    data = samples.copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data["entry_year"] = data["entry_date"].dt.year.astype("int64")
    years = test_years or sorted(int(year) for year in data["entry_year"].dropna().unique() if int(year) >= 2022)
    splits: list[WalkForwardSplit] = []
    for year in years:
        test_start = pd.Timestamp(f"{year}-01-01")
        purge_cutoff = test_start - pd.Timedelta(days=embargo_days)
        train_mask = data["entry_year"].lt(year) & data["exit_date"].lt(purge_cutoff)
        test_mask = data["entry_year"].eq(year)
        train_index = data.index[train_mask]
        test_index = data.index[test_mask]
        if len(train_index) and len(test_index):
            splits.append(WalkForwardSplit(test_year=int(year), train_index=train_index, test_index=test_index))
    return splits


def _build_model(numeric_features: list[str], categorical_features: list[str]) -> Pipeline:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=5)),
        ]
    )
    preprocess = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, numeric_features),
            ("cat", categorical_pipe, categorical_features),
        ]
    )
    clf = LogisticRegression(max_iter=1000, C=0.5, class_weight="balanced", solver="lbfgs")
    return Pipeline(steps=[("preprocess", preprocess), ("model", clf)])


def run_purged_walk_forward(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = samples.copy()
    splits = build_purged_walk_forward_splits(data)
    scored_parts: list[pd.DataFrame] = []
    feature_rows: list[dict[str, Any]] = []
    features = [column for column in NUMERIC_FEATURES + CATEGORICAL_FEATURES if column in data.columns]
    numeric_features = [column for column in NUMERIC_FEATURES if column in features]
    categorical_features = [column for column in CATEGORICAL_FEATURES if column in features]
    for split in splits:
        train = data.loc[split.train_index].copy()
        test = data.loc[split.test_index].copy()
        if len(train) < MIN_TRAIN_ROWS or train["stage015_quality_label"].nunique() < 2:
            continue
        model = _build_model(numeric_features, categorical_features)
        model.fit(train[features], train["stage015_quality_label"].astype("int64"))
        proba = model.predict_proba(test[features])[:, 1]
        test["oos_score"] = proba
        test["test_year"] = split.test_year
        test["train_rows"] = len(train)
        test["train_positive_rate"] = float(train["stage015_quality_label"].mean())
        scored_parts.append(test)
        try:
            names = model.named_steps["preprocess"].get_feature_names_out()
            coef = model.named_steps["model"].coef_[0]
            order = np.argsort(np.abs(coef))[::-1][:20]
            for rank, idx in enumerate(order, start=1):
                feature_rows.append(
                    {
                        "test_year": split.test_year,
                        "rank": rank,
                        "feature": str(names[idx]),
                        "coefficient": float(coef[idx]),
                        "abs_coefficient": float(abs(coef[idx])),
                    }
                )
        except Exception:
            pass
    scored = pd.concat(scored_parts, ignore_index=True, sort=False) if scored_parts else pd.DataFrame()
    feature_summary = pd.DataFrame(feature_rows)
    return scored, feature_summary


def assign_yearly_score_buckets(scored: pd.DataFrame) -> pd.DataFrame:
    result = scored.copy()
    result["entry_year"] = pd.to_numeric(result["entry_year"], errors="coerce").astype("int64")
    result["oos_score"] = pd.to_numeric(result["oos_score"], errors="coerce")
    result["score_rank_pct"] = result.groupby("entry_year")["oos_score"].rank(method="first", pct=True)
    result["score_bucket"] = "mid"
    result.loc[result["score_rank_pct"].le(1.0 / 3.0), "score_bucket"] = "low"
    result.loc[result["score_rank_pct"].gt(2.0 / 3.0), "score_bucket"] = "high"
    return result


def summarize_buckets(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = scored.copy()
    data["stage015_quality_label"] = _numeric(data, "stage015_quality_label", 0.0).fillna(0.0)
    data["realized_pnl"] = _numeric(data, "realized_pnl", 0.0).fillna(0.0)
    data["big_winner"] = _numeric(data, "big_winner", 0.0).fillna(0.0)
    data["bad_path"] = _numeric(data, "bad_path", 0.0).fillna(0.0)
    summary = (
        data.groupby(["entry_year", "score_bucket"], dropna=False)
        .agg(
            count=("stage015_quality_label", "size"),
            quality_rate_pct=("stage015_quality_label", lambda s: float(s.mean() * 100.0)),
            total_realized_pnl=("realized_pnl", "sum"),
            mean_realized_pnl=("realized_pnl", "mean"),
            big_winner_rate_pct=("big_winner", lambda s: float(s.mean() * 100.0)),
            bad_path_rate_pct=("bad_path", lambda s: float(s.mean() * 100.0)),
            mean_oos_score=("oos_score", "mean"),
        )
        .reset_index()
    )
    wide_parts = []
    for metric in [
        "count",
        "quality_rate_pct",
        "total_realized_pnl",
        "mean_realized_pnl",
        "big_winner_rate_pct",
        "bad_path_rate_pct",
        "mean_oos_score",
    ]:
        pivot = summary.pivot(index="entry_year", columns="score_bucket", values=metric)
        pivot.columns = [f"{metric}_{column}" for column in pivot.columns]
        wide_parts.append(pivot)
    comparison = pd.concat(wide_parts, axis=1).reset_index()
    for column in [
        "quality_rate_pct_high",
        "quality_rate_pct_low",
        "total_realized_pnl_high",
        "total_realized_pnl_low",
        "bad_path_rate_pct_high",
        "bad_path_rate_pct_low",
    ]:
        if column not in comparison.columns:
            comparison[column] = np.nan
    comparison["high_minus_low_quality_rate_pp"] = (
        comparison["quality_rate_pct_high"] - comparison["quality_rate_pct_low"]
    )
    comparison["high_minus_low_total_pnl"] = (
        comparison["total_realized_pnl_high"] - comparison["total_realized_pnl_low"]
    )
    comparison["high_minus_low_bad_path_rate_pp"] = (
        comparison["bad_path_rate_pct_high"] - comparison["bad_path_rate_pct_low"]
    )
    comparison["high_quality_beats_low"] = comparison["high_minus_low_quality_rate_pp"].gt(0.0).astype("int64")
    comparison["high_pnl_beats_low"] = comparison["high_minus_low_total_pnl"].gt(0.0).astype("int64")
    comparison["high_bad_path_below_low"] = comparison["high_minus_low_bad_path_rate_pp"].lt(0.0).astype("int64")
    return summary.sort_values(["entry_year", "score_bucket"]).reset_index(drop=True), comparison.sort_values(
        "entry_year"
    ).reset_index(drop=True)


def _decision(
    samples: pd.DataFrame,
    scored: pd.DataFrame,
    comparison: pd.DataFrame,
    input_panel_rows: int,
) -> dict[str, Any]:
    years = int(comparison["entry_year"].nunique()) if not comparison.empty else 0
    quality_beats = int(comparison["high_quality_beats_low"].sum()) if not comparison.empty else 0
    pnl_beats = int(comparison["high_pnl_beats_low"].sum()) if not comparison.empty else 0
    bad_path_better = int(comparison["high_bad_path_below_low"].sum()) if not comparison.empty else 0
    high_min_pnl = float(comparison["total_realized_pnl_high"].min()) if "total_realized_pnl_high" in comparison else np.nan
    high_total_pnl = float(comparison["total_realized_pnl_high"].sum()) if "total_realized_pnl_high" in comparison else 0.0
    low_total_pnl = float(comparison["total_realized_pnl_low"].sum()) if "total_realized_pnl_low" in comparison else 0.0
    if years >= 4 and quality_beats >= years - 1 and pnl_beats >= years - 1 and high_min_pnl > 0:
        decision = "stage015_oos_meta_label_has_add_risk_proxy_value"
        reason = "OOS 高分桶跨年稳定优于低分桶且各年高分桶 PnL 为正，可进入只读加风险 proxy。"
        continue_after = "有价值。下一步只能把 OOS 分数冻结后做非挤占 proxy，不能改模型或阈值。"
    else:
        decision = "stage015_oos_meta_label_not_stable_keep_readonly"
        reason = "OOS 高分桶没有跨年稳定优于低分桶，不能用于当前重建 C9 加风险。"
        continue_after = "有限。继续调特征、模型、桶阈值大概率是过拟合；除非引入新外生特征源。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_panel_rows": int(input_panel_rows),
        "dedup_model_rows": int(samples["actual_trade_key"].nunique()) if "actual_trade_key" in samples else int(len(samples)),
        "scored_oos_rows": int(len(scored)),
        "oos_year_count": years,
        "high_quality_beats_low_years": quality_beats,
        "high_pnl_beats_low_years": pnl_beats,
        "high_bad_path_below_low_years": bad_path_better,
        "high_total_oos_pnl": high_total_pnl,
        "low_total_oos_pnl": low_total_pnl,
        "high_min_year_pnl": high_min_pnl,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Meta-labeling should only size existing primary signals. Prior Stage236 failed on old 78-1 samples; "
            "this stage re-tests current rebuilt C9 with more samples and purged OOS only."
        ),
        "overfit_reflection_before": (
            "中等。二级模型天然容易过拟合；本阶段用去重、年份 OOS、embargo 和低复杂度逻辑回归压低风险。"
        ),
        "overfit_reflection_after": (
            "若 OOS 不稳定后继续调模型/特征/桶阈值，就是过拟合；本阶段只记录一次冻结审计。"
        ),
        "continue_value_before": "有价值。目标要求 AI 选品/高质量信号加风险，当前 C9 样本比旧 78-1 样本更大，值得一次严格复验。",
        "continue_value_after": continue_after,
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }


def _plot(comparison: pd.DataFrame) -> None:
    if comparison.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    years = comparison["entry_year"].astype(str)
    axes[0].bar(years, comparison["high_minus_low_quality_rate_pp"], color="#2563eb")
    axes[0].axhline(0.0, color="#111827", linewidth=0.8)
    axes[0].set_title("Stage015 OOS High minus Low Quality Rate")
    axes[0].set_ylabel("percentage points")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(years, comparison["high_minus_low_total_pnl"], color="#16a34a")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].set_title("Stage015 OOS High minus Low Realized PnL")
    axes[1].set_ylabel("cash pnl")
    axes[1].set_xlabel("entry year")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    bucket_summary: pd.DataFrame,
    year_comparison: pd.DataFrame,
    feature_summary: pd.DataFrame,
) -> None:
    key_metrics = {
        key: decision[key]
        for key in [
            "input_panel_rows",
            "dedup_model_rows",
            "scored_oos_rows",
            "oos_year_count",
            "high_quality_beats_low_years",
            "high_pnl_beats_low_years",
            "high_bad_path_below_low_years",
            "high_total_oos_pnl",
            "low_total_oos_pnl",
            "high_min_year_pnl",
        ]
    }
    text = f"""# Stage015 Purged Meta-label OOS Audit

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`

## 假设

当前重建 C9 的 Stage009 样本比旧 `78-1` 信号质量 AI 样本更大，因此可以重新做一次严格的 meta-label OOS 审计。模型只判断已有开仓信号质量，不产生新方向信号。

## 方法

- 样本先按实际交易去重，避免多冷启动面板重复交易泄漏。
- 训练/测试使用 expanding walk-forward；测试年之前训练，并剔除测试年前 `20` 天内仍未结束的训练样本。
- 模型为低复杂度 logistic regression，特征只使用入场前可见字段；`MFE/MAE/exit_efficiency/realized_pnl` 等事后字段不进特征。
- 每个测试年内按 OOS score 分成 low/mid/high 三桶，只看 high 是否稳定优于 low。

## 结果概要

```json
{json.dumps(_json_safe(key_metrics), ensure_ascii=False, indent=2)}
```

## 年度高低分桶对比

{_md_table(year_comparison, max_rows=20)}

## 分桶摘要

{_md_table(bucket_summary, max_rows=30)}

## 主要特征系数

{_md_table(feature_summary.head(30), max_rows=30)}

## 结论

- {decision["decision_reason"]}
- 本阶段只读，不改策略、不改 AI 池、不连接 CTP、不调用订单 API。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    bucket_summary: pd.DataFrame,
    year_comparison: pd.DataFrame,
    feature_summary: pd.DataFrame,
) -> None:
    text = f"""# Stage015 Purged Meta-label OOS Audit

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：当前重建 C9 二级信号质量模型只读 OOS 复验；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；只有 OOS 稳定后才允许进入后续 proxy/A/B

## 外部调研与判断

- 参考资料：Lopez de Prado meta-labeling、Hudson & Thames triple-barrier/meta-labeling、旧 `futures_trend_signal_quality_ai` Stage235/236 反证。
- 我的判断：二级 AI 的正确位置是给已有主信号做 sizing/approval，不是生成方向；当前 C9 样本更大，值得一次严格复验，但 OOS 不稳定就必须停止。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage015_purged_meta_label_oos_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage015_purged_meta_label_oos_audit.py`
- 新增参数：`EMBARGO_DAYS={EMBARGO_DAYS}`、`MIN_TRAIN_ROWS={MIN_TRAIN_ROWS}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- 输入 panel rows：`{decision["input_panel_rows"]}`
- 去重模型样本：`{decision["dedup_model_rows"]}`
- OOS scored rows：`{decision["scored_oos_rows"]}`
- OOS 年数：`{decision["oos_year_count"]}`
- high 质量率胜 low 年数：`{decision["high_quality_beats_low_years"]}`
- high PnL 胜 low 年数：`{decision["high_pnl_beats_low_years"]}`
- high bad_path 低于 low 年数：`{decision["high_bad_path_below_low_years"]}`
- high OOS total PnL：`{decision["high_total_oos_pnl"]:.2f}`
- low OOS total PnL：`{decision["low_total_oos_pnl"]:.2f}`
- high 最差年度 PnL：`{decision["high_min_year_pnl"]:.2f}`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## 年度高低分桶对比

{_md_table(year_comparison, max_rows=20)}

## 分桶摘要

{_md_table(bucket_summary, max_rows=30)}

## 主要特征系数

{_md_table(feature_summary.head(30), max_rows=30)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- scored_samples: `{SCORED_PATH}`
- bucket_summary: `{BUCKET_SUMMARY_PATH}`
- year_comparison: `{YEAR_COMPARISON_PATH}`
- feature_summary: `{FEATURE_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = _read_csv(STAGE009_EVENTS_PATH)
    samples = prepare_model_samples(events)
    scored, feature_summary = run_purged_walk_forward(samples)
    scored = assign_yearly_score_buckets(scored) if not scored.empty else scored
    bucket_summary, year_comparison = summarize_buckets(scored) if not scored.empty else (pd.DataFrame(), pd.DataFrame())
    decision = _decision(samples, scored, year_comparison, input_panel_rows=len(events))
    scored.to_csv(SCORED_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_comparison.to_csv(YEAR_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    feature_summary.to_csv(FEATURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(year_comparison)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, bucket_summary, year_comparison, feature_summary)
    _write_stage_record(decision, bucket_summary, year_comparison, feature_summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
