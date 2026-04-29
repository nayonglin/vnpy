from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_ai_meta_label_walkforward_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_ai_meta_label_walkforward_v1"

LABEL_COL: str = "fwd_excess_ret_10"
MODEL_NAME: str = "logistic_meta_label_expanding_yearly"
MIN_TRAIN_ROWS: int = 3_000
TEST_START_YEAR: int = 2020

NUMERIC_FEATURES: tuple[str, ...] = (
    "ret_1",
    "ret_5",
    "ret_10",
    "ret_20",
    "dist_ma20",
    "volume_ratio_20",
    "turnover_5_20_ratio",
    "turnover_20_60_ratio",
    "turnover_rate_f",
    "adv20_turnover",
    "circ_mv",
    "total_mv",
    "score_oversold_ret_5",
    "score_oversold_ret_10",
    "score_oversold_ret_20",
    "score_below_ma20",
    "score_down_volume_pressure",
    "bm_ret_1",
    "bm_ret_5",
    "bm_ret_10",
    "bm_ret_20_right",
    "bm_ret_60",
    "median_component_ret_20",
    "p20_component_ret_20",
    "bm_turnover_ratio_20",
    "bm_turnover_20_60_ratio",
    "component_turnover_20_60_ratio",
    "selected_industry_count",
    "selected_industry_stock_count",
    "candidate_count",
    "basket_weight",
)

CATEGORICAL_FEATURES: tuple[str, ...] = (
    "industry",
    "market_state_20d",
    "signal_limit_state",
    "stock_ret20_band",
    "stock_ret10_band",
    "stock_ret5_band",
    "stock_ret1_band",
    "volume_ratio20_band",
    "down_volume_pressure_band",
    "turnover_5_20_band",
    "turnover_20_60_band",
    "bm_ret_5_band",
    "bm_ret_20_band",
    "component_turnover_20_60_band",
    "top_age_bucket",
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Meta-labeling uses a secondary model to filter or size primary trading signals",
        "https://en.wikipedia.org/wiki/Meta-Labeling",
    ),
    (
        "Walk-forward validation trains on past data and tests on unseen future periods",
        "https://ml4trading.io/primer/walk-forward-validation-for-time-series/",
    ),
    (
        "Short-term residual reversal research shows reversal quality improves after removing common factor exposure",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
)


def make_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False, min_frequency=20)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def _safe_metric(fn: Any, y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    try:
        if len(np.unique(y_true)) < 2:
            return None
        return float(fn(y_true, y_score))
    except ValueError:
        return None


def _safe_log_loss(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    try:
        return float(log_loss(y_true, y_score, labels=[0, 1]))
    except ValueError:
        return None


def load_dataset() -> tuple[pd.DataFrame, list[str], list[str]]:
    selected = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    df = (
        selected.filter(pl.col("scenario") == PAPER_SCENARIO)
        .filter(pl.col(LABEL_COL).is_not_null() & pl.col(LABEL_COL).is_finite())
        .with_columns(
            pl.col("datetime").dt.year().alias("year"),
            (pl.col(LABEL_COL) > 0).cast(pl.Int8).alias("meta_label"),
        )
    )
    numeric = [col for col in NUMERIC_FEATURES if col in df.columns]
    categorical = [col for col in CATEGORICAL_FEATURES if col in df.columns]
    keep_cols_raw = [
        "datetime",
        "year",
        "symbol",
        "code_name",
        "industry",
        "scenario",
        "basket_weight",
        LABEL_COL,
        "fwd_ret_10",
        "meta_label",
        *numeric,
        *[col for col in categorical if col not in {"industry"}],
    ]
    keep_cols = list(dict.fromkeys(keep_cols_raw))
    return df.select([col for col in keep_cols if col in df.columns]).to_pandas(), numeric, categorical


def build_pipeline(numeric: list[str], categorical: list[str]) -> Pipeline:
    numeric_pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipe = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", make_one_hot_encoder()),
        ]
    )
    preprocessor = ColumnTransformer(
        [
            ("num", numeric_pipe, numeric),
            ("cat", categorical_pipe, categorical),
        ],
        remainder="drop",
    )
    model = LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5, solver="lbfgs")
    return Pipeline([("preprocessor", preprocessor), ("model", model)])


def collect_coefficients(pipe: Pipeline, fold_year: int) -> pd.DataFrame:
    preprocessor: ColumnTransformer = pipe.named_steps["preprocessor"]
    model: LogisticRegression = pipe.named_steps["model"]
    try:
        names = preprocessor.get_feature_names_out()
    except Exception:
        names = np.array([f"feature_{i}" for i in range(model.coef_.shape[1])])
    return pd.DataFrame(
        {
            "test_year": fold_year,
            "feature": names,
            "coefficient": model.coef_[0],
            "abs_coefficient": np.abs(model.coef_[0]),
        }
    )


def run_walk_forward(data: pd.DataFrame, numeric: list[str], categorical: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    years = sorted(int(year) for year in data["year"].dropna().unique() if int(year) >= TEST_START_YEAR)
    feature_cols = numeric + categorical
    fold_rows: list[dict[str, Any]] = []
    pred_frames: list[pd.DataFrame] = []
    coef_frames: list[pd.DataFrame] = []

    for year in years:
        train = data[data["year"] < year].copy()
        test = data[data["year"] == year].copy()
        if len(train) < MIN_TRAIN_ROWS or test.empty:
            continue
        pipe = build_pipeline(numeric, categorical)
        pipe.fit(train[feature_cols], train["meta_label"].astype(int))
        probability = pipe.predict_proba(test[feature_cols])[:, 1]
        test = test.copy()
        test["meta_probability"] = probability
        test["test_year"] = year
        test["prob_rank_pct_by_day"] = test.groupby("datetime")["meta_probability"].rank(pct=True, method="first")
        pred_frames.append(test)
        coef_frames.append(collect_coefficients(pipe, year))

        y_true = test["meta_label"].astype(int).to_numpy()
        fold_rows.append(
            {
                "test_year": year,
                "train_rows": len(train),
                "test_rows": len(test),
                "train_start": str(train["datetime"].min()),
                "train_end": str(train["datetime"].max()),
                "test_start": str(test["datetime"].min()),
                "test_end": str(test["datetime"].max()),
                "positive_rate": float(test["meta_label"].mean()),
                "roc_auc": _safe_metric(roc_auc_score, y_true, probability),
                "average_precision": _safe_metric(average_precision_score, y_true, probability),
                "log_loss": _safe_log_loss(y_true, probability),
                "baseline_mean_excess10": float(test[LABEL_COL].mean()),
                "top50_mean_excess10": float(test.loc[test["prob_rank_pct_by_day"] >= 0.5, LABEL_COL].mean()),
                "top30_mean_excess10": float(test.loc[test["prob_rank_pct_by_day"] >= 0.7, LABEL_COL].mean()),
                "top20_mean_excess10": float(test.loc[test["prob_rank_pct_by_day"] >= 0.8, LABEL_COL].mean()),
            }
        )
    if not pred_frames:
        raise RuntimeError("No valid walk-forward folds.")
    predictions = pd.concat(pred_frames, ignore_index=True, sort=False)
    coefficients = pd.concat(coef_frames, ignore_index=True, sort=False) if coef_frames else pd.DataFrame()
    return pd.DataFrame(fold_rows), predictions, coefficients


def build_lift_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cuts = [
        ("all_candidates", 0.0),
        ("top50_by_day", 0.5),
        ("top30_by_day", 0.7),
        ("top20_by_day", 0.8),
    ]
    for name, threshold in cuts:
        subset = predictions[predictions["prob_rank_pct_by_day"] >= threshold]
        rows.append(
            {
                "bucket": name,
                "rows": len(subset),
                "coverage_ratio": len(subset) / len(predictions) if len(predictions) else 0.0,
                "positive_rate": float(subset["meta_label"].mean()) if len(subset) else 0.0,
                "mean_fwd_excess_ret_10": float(subset[LABEL_COL].mean()) if len(subset) else 0.0,
                "mean_fwd_ret_10": float(subset["fwd_ret_10"].mean()) if len(subset) and "fwd_ret_10" in subset else 0.0,
                "median_probability": float(subset["meta_probability"].median()) if len(subset) else 0.0,
            }
        )
    result = pd.DataFrame(rows)
    baseline = result.loc[result["bucket"] == "all_candidates"].iloc[0]
    result["excess_ret_lift_vs_all"] = result["mean_fwd_excess_ret_10"] - baseline["mean_fwd_excess_ret_10"]
    result["positive_rate_lift_vs_all"] = result["positive_rate"] - baseline["positive_rate"]
    return result


def build_daily_lift(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dt, group in predictions.groupby("datetime"):
        base = group[LABEL_COL].mean()
        for name, threshold in [("top50_by_day", 0.5), ("top30_by_day", 0.7), ("top20_by_day", 0.8)]:
            subset = group[group["prob_rank_pct_by_day"] >= threshold]
            if subset.empty:
                continue
            rows.append(
                {
                    "datetime": dt,
                    "bucket": name,
                    "rows": len(subset),
                    "all_mean_fwd_excess_ret_10": base,
                    "bucket_mean_fwd_excess_ret_10": subset[LABEL_COL].mean(),
                    "lift": subset[LABEL_COL].mean() - base,
                }
            )
    return pd.DataFrame(rows)


def summarize_daily_lift(daily_lift: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, group in daily_lift.groupby("bucket"):
        rows.append(
            {
                "bucket": bucket,
                "days": len(group),
                "avg_lift": float(group["lift"].mean()),
                "median_lift": float(group["lift"].median()),
                "lift_win_rate": float((group["lift"] > 0).mean()),
                "avg_bucket_rows": float(group["rows"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("bucket")


def summarize_coefficients(coefficients: pd.DataFrame) -> pd.DataFrame:
    if coefficients.empty:
        return pd.DataFrame()
    return (
        coefficients.groupby("feature", as_index=False)
        .agg(
            mean_coefficient=("coefficient", "mean"),
            mean_abs_coefficient=("abs_coefficient", "mean"),
            folds=("test_year", "nunique"),
        )
        .sort_values("mean_abs_coefficient", ascending=False)
        .head(80)
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "walk_forward_fold_count",
            "status": "pass" if summary["fold_count"] >= 4 else "warn",
            "value": str(summary["fold_count"]),
            "expected": ">=4",
            "note": "AI方向必须多个未来年份测试，不能单切分。",
        },
        {
            "checkpoint": "auc_above_random",
            "status": "pass" if summary["mean_roc_auc"] > 0.52 else "warn",
            "value": f"{summary['mean_roc_auc']:.4f}",
            "expected": ">0.52",
            "note": "候选级模型至少要略高于随机，否则不应接入。",
        },
        {
            "checkpoint": "top30_positive_lift_positive",
            "status": "pass" if summary["top30_positive_rate_lift"] > 0 else "warn",
            "value": pct(summary["top30_positive_rate_lift"]),
            "expected": ">0",
            "note": "高置信候选的正样本率应高于全体候选。",
        },
        {
            "checkpoint": "top30_excess_ret_lift_positive",
            "status": "pass" if summary["top30_excess_ret_lift"] > 0 else "warn",
            "value": pct(summary["top30_excess_ret_lift"]),
            "expected": ">0",
            "note": "高置信候选的10日超额收益均值应高于全体候选。",
        },
        {
            "checkpoint": "no_strategy_integration",
            "status": "pass",
            "value": "analysis_only",
            "expected": "analysis_only",
            "note": "本阶段只做AI可行性验证，不接入paper或实盘。",
        },
    ]
    return pl.DataFrame(rows)


def _md(frame: pd.DataFrame | pl.DataFrame, columns: list[str] | None = None, max_rows: int = 80) -> str:
    if isinstance(frame, pd.DataFrame):
        if frame.empty:
            return "无数据"
        work = frame if columns is None else frame[[col for col in columns if col in frame.columns]]
        return work.head(max_rows).to_markdown(index=False)
    if frame.is_empty():
        return "无数据"
    use_cols = frame.columns if columns is None else columns
    return markdown_table(frame, use_cols, max_rows=max_rows)


def write_report(
    summary: dict[str, Any],
    fold_summary: pd.DataFrame,
    lift_summary: pd.DataFrame,
    daily_lift_summary: pd.DataFrame,
    coef_summary: pd.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 AI元标签walk-forward实验 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：AI/meta-label可行性验证；不新增交易规则、不修改paper入口、不调收益参数。",
        f"- 模型：`{MODEL_NAME}`。",
        f"- 标签：`{LABEL_COL} > 0`。",
        "- A/B判断：股票震荡独立研究，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- AI更适合做二级过滤/仓位置信度，而不是直接预测方向替代主策略。",
        "- 金融时间序列不能随机切分，必须walk-forward，且预处理器在每个训练窗内单独拟合。",
        "- 残差反转文献说明反转信号质量与市场/行业共同暴露有关，因此本实验加入市场、行业、量价状态特征。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 样本`{summary['sample_rows']}`行，测试折数`{summary['fold_count']}`个，测试年份`{summary['test_year_start']}`-`{summary['test_year_end']}`。",
            f"- 平均AUC `{summary['mean_roc_auc']:.4f}`，平均AP `{summary['mean_average_precision']:.4f}`。",
            f"- 全体候选10日超额收益均值`{pct(summary['all_mean_fwd_excess_ret_10'])}`；top30按日高置信候选均值`{pct(summary['top30_mean_fwd_excess_ret_10'])}`，提升`{pct(summary['top30_excess_ret_lift'])}`。",
            f"- 全体候选正样本率`{pct(summary['all_positive_rate'])}`；top30正样本率`{pct(summary['top30_positive_rate'])}`，提升`{pct(summary['top30_positive_rate_lift'])}`。",
            f"- top30按日lift胜率`{pct(summary['top30_daily_lift_win_rate'])}`。",
            "",
            "## 判断",
            "",
            "- 这是候选级AI过滤验证，不是完整资金曲线；通过也不能直接接入。",
            "- 如果top30正样本率和超额收益lift稳定为正，下一步才值得做“AI只过滤买不到/低置信候选”的组合回放。",
            "- 如果lift不稳定或只集中在单一年份，应判定为噪声，不继续接入。",
            "",
            "## 年度walk-forward",
            "",
            _md(
                fold_summary,
                [
                    "test_year",
                    "train_rows",
                    "test_rows",
                    "positive_rate",
                    "roc_auc",
                    "average_precision",
                    "baseline_mean_excess10",
                    "top50_mean_excess10",
                    "top30_mean_excess10",
                    "top20_mean_excess10",
                ],
            ),
            "",
            "## Lift汇总",
            "",
            _md(lift_summary),
            "",
            "## 按日Lift",
            "",
            _md(daily_lift_summary),
            "",
            "## 主要特征系数",
            "",
            _md(coef_summary, max_rows=30),
            "",
            "## 质量检查",
            "",
            _md(quality),
            "",
            "## 失败项",
            "",
            _md(quality.filter(pl.col("status") == "fail")),
            "",
            "## 警告项",
            "",
            _md(quality.filter(pl.col("status") == "warn")),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：是，天然高风险。",
            "- 原因：AI模型自由度高，若随机切分或反复试阈值，会快速变成拟合噪声。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：待观察，但本阶段已降低风险。",
            "- 原因：采用逐年walk-forward、每折独立fit预处理器和模型，且不把结果接入交易。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：当前30万口径年化偏低，AI若能提高候选质量，可作为非参数硬调优之外的方向。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：取决于lift是否稳定。",
            "- 原因：只有跨年份稳定高置信lift为正，才值得进入组合回放。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不修改30万paper入口。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data, numeric, categorical = load_dataset()
    fold_summary, predictions, coefficients = run_walk_forward(data, numeric, categorical)
    lift_summary = build_lift_summary(predictions)
    daily_lift = build_daily_lift(predictions)
    daily_lift_summary = summarize_daily_lift(daily_lift)
    coef_summary = summarize_coefficients(coefficients)

    mean_roc_auc = float(fold_summary["roc_auc"].dropna().mean())
    mean_ap = float(fold_summary["average_precision"].dropna().mean())
    top30 = lift_summary[lift_summary["bucket"] == "top30_by_day"].iloc[0]
    all_candidates = lift_summary[lift_summary["bucket"] == "all_candidates"].iloc[0]
    top30_daily = daily_lift_summary[daily_lift_summary["bucket"] == "top30_by_day"].iloc[0]
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model_name": MODEL_NAME,
        "label_col": LABEL_COL,
        "sample_rows": int(len(data)),
        "numeric_features": numeric,
        "categorical_features": categorical,
        "feature_count_raw": len(numeric) + len(categorical),
        "fold_count": int(len(fold_summary)),
        "test_year_start": int(fold_summary["test_year"].min()),
        "test_year_end": int(fold_summary["test_year"].max()),
        "mean_roc_auc": mean_roc_auc,
        "mean_average_precision": mean_ap,
        "all_mean_fwd_excess_ret_10": float(all_candidates["mean_fwd_excess_ret_10"]),
        "top30_mean_fwd_excess_ret_10": float(top30["mean_fwd_excess_ret_10"]),
        "top30_excess_ret_lift": float(top30["excess_ret_lift_vs_all"]),
        "all_positive_rate": float(all_candidates["positive_rate"]),
        "top30_positive_rate": float(top30["positive_rate"]),
        "top30_positive_rate_lift": float(top30["positive_rate_lift_vs_all"]),
        "top30_daily_lift_win_rate": float(top30_daily["lift_win_rate"]),
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "fold_summary": OUTPUT_DIR / f"{PREFIX}_fold_summary.csv",
        "lift_summary": OUTPUT_DIR / f"{PREFIX}_lift_summary.csv",
        "daily_lift": OUTPUT_DIR / f"{PREFIX}_daily_lift.csv",
        "daily_lift_summary": OUTPUT_DIR / f"{PREFIX}_daily_lift_summary.csv",
        "feature_coefficients": OUTPUT_DIR / f"{PREFIX}_feature_coefficients.csv",
        "feature_coefficient_summary": OUTPUT_DIR / f"{PREFIX}_feature_coefficient_summary.csv",
        "predictions": OUTPUT_DIR / f"{PREFIX}_predictions.parquet",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    fold_summary.to_csv(paths["fold_summary"], index=False)
    lift_summary.to_csv(paths["lift_summary"], index=False)
    daily_lift.to_csv(paths["daily_lift"], index=False)
    daily_lift_summary.to_csv(paths["daily_lift_summary"], index=False)
    coefficients.to_csv(paths["feature_coefficients"], index=False)
    coef_summary.to_csv(paths["feature_coefficient_summary"], index=False)
    pl.from_pandas(predictions).write_parquet(paths["predictions"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    paths["meta"].write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "research_sources": RESEARCH_SOURCES,
                "note": "AI meta-label walk-forward feasibility only; no trading integration.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = write_report(summary, fold_summary, lift_summary, daily_lift_summary, coef_summary, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
