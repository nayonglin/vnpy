from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_SHORT_ALIAS,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage235_signal_quality_walk_forward_v1"
OUTPUT_PREFIX = "qmt_roll_stage235_signal_quality_walk_forward"
STAGE234_PREFIX = "qmt_roll_stage234_signal_quality_ai_feasibility"
STAGE234_TAG = "stage234_signal_quality_ai_feasibility_v1"

SAMPLES_INPUT_PATH = OUTPUT_DIR / f"{STAGE234_PREFIX}_samples_{STAGE234_TAG}.csv"

SCORED_SAMPLES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scored_samples_{MODEL_TAG}.csv"
WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
SCORE_BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_bucket_summary_{MODEL_TAG}.csv"
FEATURE_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_quality_table_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json"

FEATURE_COLS = [
    "direction_key",
    "signal",
    "ai_rank_bucket",
    "rsi_bucket",
    "portfolio_dd_bucket",
    "corr_bucket",
]

WALK_FORWARD_WINDOWS = [
    {"window_name": "wf_2023_train_2020_2022", "train_start": 2020, "train_end": 2022, "test_start": 2023, "test_end": 2023},
    {"window_name": "wf_2024_train_2020_2023", "train_start": 2020, "train_end": 2023, "test_start": 2024, "test_end": 2024},
    {"window_name": "wf_2025_train_2020_2024", "train_start": 2020, "train_end": 2024, "test_start": 2025, "test_end": 2025},
    {"window_name": "wf_2026_train_2020_2025", "train_start": 2020, "train_end": 2025, "test_start": 2026, "test_end": 2026},
]


def _to_markdown(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    return df.head(max_rows).to_markdown(index=False)


def _clean_bucket(series: pd.Series, fallback: str = "missing") -> pd.Series:
    cleaned = series.astype(str).replace({"nan": fallback, "None": fallback, "": fallback})
    return cleaned.fillna(fallback)


def load_samples() -> pd.DataFrame:
    samples = pd.read_csv(SAMPLES_INPUT_PATH)
    samples["entry_date"] = pd.to_datetime(samples["entry_date"].astype(str).str.slice(0, 10)).dt.normalize()
    samples["entry_year"] = pd.to_numeric(samples["entry_year"], errors="coerce").astype(int)
    samples["meta_success"] = pd.to_numeric(samples["meta_success"], errors="coerce").fillna(0).astype(int)
    samples["realized_pnl"] = pd.to_numeric(samples["realized_pnl"], errors="coerce").fillna(0.0)
    samples["risk_reward_proxy"] = pd.to_numeric(samples["risk_reward_proxy"], errors="coerce")
    samples["portfolio_drawdown_pct"] = pd.to_numeric(samples.get("portfolio_drawdown_pct"), errors="coerce").fillna(0.0)
    samples["same_direction_correlation_max_corr"] = pd.to_numeric(
        samples.get("same_direction_correlation_max_corr"),
        errors="coerce",
    ).fillna(0.0)
    samples["portfolio_dd_bucket"] = pd.cut(
        samples["portfolio_drawdown_pct"],
        bins=[-np.inf, 0.05, 0.15, np.inf],
        labels=["dd_lt_5", "dd_5_15", "dd_gt_15"],
    ).astype(str)
    samples["corr_bucket"] = pd.cut(
        samples["same_direction_correlation_max_corr"],
        bins=[-np.inf, 0.4, 0.7, np.inf],
        labels=["corr_lt_04", "corr_04_07", "corr_gt_07"],
    ).astype(str)
    for col in FEATURE_COLS:
        samples[col] = _clean_bucket(samples[col])
    samples = samples.sort_values(["entry_date", "vt_symbol", "direction_key"]).reset_index(drop=True)
    return samples


def build_feature_quality_table(train: pd.DataFrame, min_count: int = 12, shrinkage: float = 20.0) -> pd.DataFrame:
    global_success = float(train["meta_success"].mean())
    global_rr = float(train["risk_reward_proxy"].replace([np.inf, -np.inf], np.nan).mean())
    if np.isnan(global_rr):
        global_rr = 0.0

    rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLS:
        grouped = (
            train.groupby(feature, dropna=False)
            .agg(
                sample_count=("meta_success", "size"),
                success_rate=("meta_success", "mean"),
                avg_realized_pnl=("realized_pnl", "mean"),
                avg_risk_reward_proxy=("risk_reward_proxy", "mean"),
            )
            .reset_index()
            .rename(columns={feature: "feature_value"})
        )
        for _, row in grouped.iterrows():
            count = float(row["sample_count"])
            success_rate = float(row["success_rate"])
            avg_rr = float(row["avg_risk_reward_proxy"])
            if np.isnan(avg_rr):
                avg_rr = global_rr
            shrunk_success = (success_rate * count + global_success * shrinkage) / (count + shrinkage)
            shrunk_rr = (avg_rr * count + global_rr * shrinkage) / (count + shrinkage)
            support_weight = min(1.0, count / float(min_count))
            quality_score = (shrunk_success - global_success) + 0.08 * np.tanh(shrunk_rr)
            quality_score *= support_weight
            rows.append(
                {
                    "feature_name": feature,
                    "feature_value": str(row["feature_value"]),
                    "sample_count": int(row["sample_count"]),
                    "success_rate_pct": success_rate * 100.0,
                    "avg_realized_pnl": float(row["avg_realized_pnl"]),
                    "avg_risk_reward_proxy": avg_rr,
                    "shrunk_success_rate_pct": shrunk_success * 100.0,
                    "shrunk_risk_reward_proxy": shrunk_rr,
                    "support_weight": support_weight,
                    "quality_score": quality_score,
                    "global_success_rate_pct": global_success * 100.0,
                }
            )
    return pd.DataFrame(rows)


def score_test_samples(test: pd.DataFrame, quality_table: pd.DataFrame) -> pd.DataFrame:
    score_maps = {
        feature: dict(zip(group["feature_value"].astype(str), group["quality_score"]))
        for feature, group in quality_table.groupby("feature_name")
    }
    scored = test.copy()
    score_components: list[pd.Series] = []
    for feature in FEATURE_COLS:
        component = scored[feature].astype(str).map(score_maps.get(feature, {})).fillna(0.0)
        scored[f"score_{feature}"] = component
        score_components.append(component)
    scored["quality_score"] = np.vstack([s.to_numpy(dtype=float) for s in score_components]).mean(axis=0)
    return scored


def assign_score_bucket(scored: pd.DataFrame) -> pd.DataFrame:
    scored = scored.copy()
    if len(scored) < 3 or scored["quality_score"].nunique() < 3:
        scored["score_bucket"] = "all"
        return scored
    ranked = scored["quality_score"].rank(method="first", ascending=True)
    scored["score_bucket"] = pd.qcut(ranked, q=3, labels=["low", "mid", "high"]).astype(str)
    return scored


def summarize_bucket(df: pd.DataFrame, group_cols: list[str], big_winner_threshold: float) -> pd.DataFrame:
    grouped = (
        df.groupby(group_cols, dropna=False)
        .agg(
            sample_count=("meta_success", "size"),
            success_rate_pct=("meta_success", lambda s: float(s.mean() * 100.0)),
            avg_realized_pnl=("realized_pnl", "mean"),
            median_realized_pnl=("realized_pnl", "median"),
            pnl_sum=("realized_pnl", "sum"),
            avg_quality_score=("quality_score", "mean"),
            big_winner_count=("realized_pnl", lambda s: int((s >= big_winner_threshold).sum())),
        )
        .reset_index()
    )
    return grouped


def run_walk_forward(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scored_rows: list[pd.DataFrame] = []
    feature_tables: list[pd.DataFrame] = []
    window_rows: list[dict[str, Any]] = []
    bucket_rows: list[pd.DataFrame] = []

    positive_train = samples.loc[samples["realized_pnl"] > 0, "realized_pnl"]
    big_winner_threshold = float(positive_train.quantile(0.80)) if not positive_train.empty else float("inf")

    for window in WALK_FORWARD_WINDOWS:
        train = samples[(samples["entry_year"] >= window["train_start"]) & (samples["entry_year"] <= window["train_end"])].copy()
        test = samples[(samples["entry_year"] >= window["test_start"]) & (samples["entry_year"] <= window["test_end"])].copy()
        if train.empty or test.empty:
            continue

        feature_table = build_feature_quality_table(train)
        feature_table["window_name"] = window["window_name"]
        feature_table["train_start"] = window["train_start"]
        feature_table["train_end"] = window["train_end"]
        feature_tables.append(feature_table)

        scored = score_test_samples(test, feature_table)
        scored = assign_score_bucket(scored)
        scored["window_name"] = window["window_name"]
        scored["train_start"] = window["train_start"]
        scored["train_end"] = window["train_end"]
        scored["test_start"] = window["test_start"]
        scored["test_end"] = window["test_end"]
        scored_rows.append(scored)

        bucket_summary = summarize_bucket(scored, ["window_name", "score_bucket"], big_winner_threshold)
        bucket_summary["train_years"] = f"{window['train_start']}-{window['train_end']}"
        bucket_summary["test_years"] = f"{window['test_start']}-{window['test_end']}"
        bucket_rows.append(bucket_summary)

        high = scored[scored["score_bucket"].eq("high")]
        low = scored[scored["score_bucket"].eq("low")]
        all_success = float(scored["meta_success"].mean() * 100.0)
        high_success = float(high["meta_success"].mean() * 100.0) if not high.empty else np.nan
        low_success = float(low["meta_success"].mean() * 100.0) if not low.empty else np.nan
        high_pnl = float(high["realized_pnl"].mean()) if not high.empty else np.nan
        low_pnl = float(low["realized_pnl"].mean()) if not low.empty else np.nan
        high_big_winners = int((high["realized_pnl"] >= big_winner_threshold).sum()) if not high.empty else 0
        all_big_winners = int((scored["realized_pnl"] >= big_winner_threshold).sum())
        window_rows.append(
            {
                "window_name": window["window_name"],
                "train_years": f"{window['train_start']}-{window['train_end']}",
                "test_years": f"{window['test_start']}-{window['test_end']}",
                "train_sample_count": int(len(train)),
                "test_sample_count": int(len(scored)),
                "all_success_rate_pct": all_success,
                "high_success_rate_pct": high_success,
                "low_success_rate_pct": low_success,
                "high_minus_low_success_pct": high_success - low_success if not np.isnan(high_success) and not np.isnan(low_success) else np.nan,
                "all_avg_realized_pnl": float(scored["realized_pnl"].mean()),
                "high_avg_realized_pnl": high_pnl,
                "low_avg_realized_pnl": low_pnl,
                "high_minus_low_avg_pnl": high_pnl - low_pnl if not np.isnan(high_pnl) and not np.isnan(low_pnl) else np.nan,
                "all_pnl_sum": float(scored["realized_pnl"].sum()),
                "high_pnl_sum": float(high["realized_pnl"].sum()) if not high.empty else 0.0,
                "low_pnl_sum": float(low["realized_pnl"].sum()) if not low.empty else 0.0,
                "all_big_winner_count": all_big_winners,
                "high_big_winner_count": high_big_winners,
                "high_big_winner_capture_pct": (high_big_winners / all_big_winners * 100.0) if all_big_winners else 0.0,
            }
        )

    scored_samples = pd.concat(scored_rows, ignore_index=True) if scored_rows else pd.DataFrame()
    feature_quality = pd.concat(feature_tables, ignore_index=True) if feature_tables else pd.DataFrame()
    window_summary = pd.DataFrame(window_rows)
    bucket_summary = pd.concat(bucket_rows, ignore_index=True) if bucket_rows else pd.DataFrame()
    return scored_samples, window_summary, bucket_summary, feature_quality


def build_report(
    scored_samples: pd.DataFrame,
    window_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    feature_quality: pd.DataFrame,
) -> str:
    high_rows = bucket_summary[bucket_summary["score_bucket"].eq("high")].copy() if not bucket_summary.empty else pd.DataFrame()
    low_rows = bucket_summary[bucket_summary["score_bucket"].eq("low")].copy() if not bucket_summary.empty else pd.DataFrame()
    lines = [
        "# Stage235 Walk-forward 信号质量基线",
        "",
        "## 口径",
        "",
        f"- 基准：`{OFFICIAL_STAGE78_SHORT_ALIAS}` / `{OFFICIAL_STAGE78_VERSION}`",
        "- 方法：只用过去窗口统计特征桶质量，再给下一年真实开仓信号打分。",
        "- 特征：`direction_key`、`signal`、`ai_rank_bucket`、`rsi_bucket`、`portfolio_dd_bucket`、`corr_bucket`。",
        "- 标签：沿用 Stage234 FIFO round-trip `gross_pnl>0`。",
        "- 注意：本阶段不是正式回测，也不接入 `risk_multiplier`。",
        "",
        "## Walk-forward 窗口结果",
        "",
        _to_markdown(window_summary),
        "",
        "## 分数桶结果",
        "",
        _to_markdown(bucket_summary, max_rows=80),
        "",
        "## 高分桶",
        "",
        _to_markdown(high_rows),
        "",
        "## 低分桶",
        "",
        _to_markdown(low_rows),
        "",
        "## 初步判断",
        "",
        f"- 样本数：`{len(scored_samples)}` 个 OOS scored samples。",
        "- 若高分桶在多数年份同时提升成功率、平均盈亏并保留大赢家，则二级模型方向成立。",
        "- 若只在少数年份有效，或高分桶漏掉大赢家，则不能接入仓位倍率。",
        "",
    ]
    if not feature_quality.empty:
        top_features = feature_quality.sort_values("quality_score", ascending=False).head(20)
        lines.extend(["## 训练期高质量特征桶样例", "", _to_markdown(top_features, max_rows=20), ""])
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = load_samples()
    scored_samples, window_summary, bucket_summary, feature_quality = run_walk_forward(samples)

    scored_samples.to_csv(SCORED_SAMPLES_PATH, index=False, encoding="utf-8-sig")
    window_summary.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(SCORE_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_quality.to_csv(FEATURE_TABLE_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(
        build_report(scored_samples, window_summary, bucket_summary, feature_quality),
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "official_manifest": build_official_stage78_manifest(),
                "base_risk_ratio": BASE_RISK_RATIO,
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "input": str(SAMPLES_INPUT_PATH.resolve()),
                "feature_cols": FEATURE_COLS,
                "walk_forward_windows": WALK_FORWARD_WINDOWS,
                "paths": {
                    "scored_samples": str(SCORED_SAMPLES_PATH.resolve()),
                    "window_summary": str(WINDOW_SUMMARY_PATH.resolve()),
                    "score_bucket_summary": str(SCORE_BUCKET_SUMMARY_PATH.resolve()),
                    "feature_quality_table": str(FEATURE_TABLE_PATH.resolve()),
                    "report": str(REPORT_PATH.resolve()),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(REPORT_PATH.resolve())
    print(window_summary.to_string(index=False))
    print(bucket_summary.to_string(index=False))


if __name__ == "__main__":
    main()
