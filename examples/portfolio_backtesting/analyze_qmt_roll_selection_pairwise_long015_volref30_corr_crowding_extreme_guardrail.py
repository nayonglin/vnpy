from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from build_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_report import (
    OUTCOME_METRIC,
    add_warning_flags,
    load_state,
    to_markdown_table,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail"

EVENTS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events.csv"
BY_YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_year.csv"
BY_SCORE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_score.csv"
YEAR_REMOVAL_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_removal.csv"
PERMUTATION_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_permutation_summary.json"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report.md"

EXTREME_NEGATIVE_THRESHOLD: float = -10_000.0
NEGATIVE_THRESHOLD: float = 0.0
PERMUTATION_COUNT: int = 10_000
RANDOM_SEED: int = 42


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def add_guardrail_targets(df: pd.DataFrame) -> pd.DataFrame:
    result = add_warning_flags(df).copy()
    result["is_severe_watch"] = result["trend_expansion_warning_label"] == "severe_watch"
    result["target_negative20"] = result[OUTCOME_METRIC] <= NEGATIVE_THRESHOLD
    result["target_extreme_negative20"] = result[OUTCOME_METRIC] <= EXTREME_NEGATIVE_THRESHOLD
    result["target_large_positive20"] = result[OUTCOME_METRIC] >= abs(EXTREME_NEGATIVE_THRESHOLD)
    return result


def summarize_alert(df: pd.DataFrame, target_column: str) -> dict[str, Any]:
    alert = df["is_severe_watch"].astype(bool)
    target = df[target_column].astype(bool)
    tp = int((alert & target).sum())
    fp = int((alert & ~target).sum())
    fn = int((~alert & target).sum())
    tn = int((~alert & ~target).sum())
    alert_count = tp + fp
    target_count = tp + fn
    non_target_count = fp + tn

    severe_df = df[alert].copy()
    non_severe_df = df[~alert].copy()
    return {
        "target_column": target_column,
        "row_count": int(len(df)),
        "alert_count": alert_count,
        "target_count": target_count,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "precision": _safe_float(tp / alert_count) if alert_count else 0.0,
        "recall": _safe_float(tp / target_count) if target_count else 0.0,
        "false_positive_rate": _safe_float(fp / non_target_count) if non_target_count else 0.0,
        "target_base_rate": _safe_float(target.mean()),
        "alert_target_lift": _safe_float((tp / alert_count) / target.mean()) if alert_count and target.mean() else 0.0,
        "severe_mean_fwd20": _safe_float(severe_df[OUTCOME_METRIC].mean()) if not severe_df.empty else 0.0,
        "non_severe_mean_fwd20": _safe_float(non_severe_df[OUTCOME_METRIC].mean()) if not non_severe_df.empty else 0.0,
        "mean_fwd20_diff_severe_minus_non": _safe_float(
            severe_df[OUTCOME_METRIC].mean() - non_severe_df[OUTCOME_METRIC].mean()
        )
        if not severe_df.empty and not non_severe_df.empty
        else 0.0,
        "severe_hit_rate_fwd20": _safe_float((severe_df[OUTCOME_METRIC] > 0).mean()) if not severe_df.empty else 0.0,
        "non_severe_hit_rate_fwd20": _safe_float((non_severe_df[OUTCOME_METRIC] > 0).mean())
        if not non_severe_df.empty
        else 0.0,
    }


def summarize_by_year(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group_df in df.groupby("year", sort=True):
        severe_df = group_df[group_df["is_severe_watch"]].copy()
        non_severe_df = group_df[~group_df["is_severe_watch"]].copy()
        rows.append(
            {
                "year": int(year),
                "date_count": int(len(group_df)),
                "severe_count": int(len(severe_df)),
                "negative_count": int(group_df["target_negative20"].sum()),
                "extreme_negative_count": int(group_df["target_extreme_negative20"].sum()),
                "mean_fwd20": _safe_float(group_df[OUTCOME_METRIC].mean()),
                "median_fwd20": _safe_float(group_df[OUTCOME_METRIC].median()),
                "hit_rate_fwd20": _safe_float((group_df[OUTCOME_METRIC] > 0).mean()),
                "severe_mean_fwd20": _safe_float(severe_df[OUTCOME_METRIC].mean()) if not severe_df.empty else 0.0,
                "non_severe_mean_fwd20": _safe_float(non_severe_df[OUTCOME_METRIC].mean())
                if not non_severe_df.empty
                else 0.0,
                "severe_extreme_negative_precision": _safe_float(severe_df["target_extreme_negative20"].mean())
                if not severe_df.empty
                else 0.0,
                "severe_negative_precision": _safe_float(severe_df["target_negative20"].mean())
                if not severe_df.empty
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def summarize_by_score(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("trend_expansion_warning_score", observed=False)
        .agg(
            date_count=("date", "size"),
            mean_fwd20=(OUTCOME_METRIC, "mean"),
            median_fwd20=(OUTCOME_METRIC, "median"),
            hit_rate_fwd20=(OUTCOME_METRIC, lambda values: float((values > 0).mean())),
            negative_rate=("target_negative20", "mean"),
            extreme_negative_rate=("target_extreme_negative20", "mean"),
            avg_rsi=("avg_rsi", "mean"),
            avg_breakout_rate=("breakout_rate", "mean"),
            avg_range_zscore=("avg_range_zscore", "mean"),
            avg_ret20_zscore=("avg_ret20_zscore", "mean"),
            avg_active_count=("avg_active_count", "mean"),
            avg_loss_streak=("avg_loss_streak", "mean"),
        )
        .reset_index()
    )


def build_year_removal(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for removed_year in sorted(df["year"].unique()):
        subset_df = df[df["year"] != removed_year].copy()
        negative_summary = summarize_alert(subset_df, "target_negative20")
        extreme_summary = summarize_alert(subset_df, "target_extreme_negative20")
        rows.append(
            {
                "removed_year": int(removed_year),
                "remaining_rows": int(len(subset_df)),
                "negative_precision": negative_summary["precision"],
                "negative_recall": negative_summary["recall"],
                "extreme_precision": extreme_summary["precision"],
                "extreme_recall": extreme_summary["recall"],
                "mean_fwd20_diff_severe_minus_non": negative_summary["mean_fwd20_diff_severe_minus_non"],
            }
        )
    return pd.DataFrame(rows)


def run_permutation(df: pd.DataFrame) -> dict[str, Any]:
    rng = np.random.default_rng(RANDOM_SEED)
    severe_count = int(df["is_severe_watch"].sum())
    outcomes = df[OUTCOME_METRIC].to_numpy(dtype="float64")
    extreme_targets = df["target_extreme_negative20"].to_numpy(dtype="int64")
    negative_targets = df["target_negative20"].to_numpy(dtype="int64")
    row_count = len(df)

    observed_alert = df["is_severe_watch"].to_numpy(dtype=bool)
    observed_diff = outcomes[observed_alert].mean() - outcomes[~observed_alert].mean()
    observed_extreme_precision = extreme_targets[observed_alert].mean()
    observed_negative_precision = negative_targets[observed_alert].mean()

    random_diffs = np.empty(PERMUTATION_COUNT, dtype="float64")
    random_extreme_precision = np.empty(PERMUTATION_COUNT, dtype="float64")
    random_negative_precision = np.empty(PERMUTATION_COUNT, dtype="float64")
    for index in range(PERMUTATION_COUNT):
        chosen = np.zeros(row_count, dtype=bool)
        chosen_indices = rng.choice(row_count, size=severe_count, replace=False)
        chosen[chosen_indices] = True
        random_diffs[index] = outcomes[chosen].mean() - outcomes[~chosen].mean()
        random_extreme_precision[index] = extreme_targets[chosen].mean()
        random_negative_precision[index] = negative_targets[chosen].mean()

    return {
        "permutation_count": PERMUTATION_COUNT,
        "random_seed": RANDOM_SEED,
        "severe_count": severe_count,
        "observed_mean_fwd20_diff_severe_minus_non": _safe_float(observed_diff),
        "p_value_random_diff_le_observed": _safe_float((random_diffs <= observed_diff).mean()),
        "random_diff_p05": _safe_float(np.quantile(random_diffs, 0.05)),
        "random_diff_p50": _safe_float(np.quantile(random_diffs, 0.50)),
        "random_diff_p95": _safe_float(np.quantile(random_diffs, 0.95)),
        "observed_extreme_negative_precision": _safe_float(observed_extreme_precision),
        "p_value_random_extreme_precision_ge_observed": _safe_float(
            (random_extreme_precision >= observed_extreme_precision).mean()
        ),
        "random_extreme_precision_p50": _safe_float(np.quantile(random_extreme_precision, 0.50)),
        "random_extreme_precision_p95": _safe_float(np.quantile(random_extreme_precision, 0.95)),
        "observed_negative_precision": _safe_float(observed_negative_precision),
        "p_value_random_negative_precision_ge_observed": _safe_float(
            (random_negative_precision >= observed_negative_precision).mean()
        ),
        "random_negative_precision_p50": _safe_float(np.quantile(random_negative_precision, 0.50)),
        "random_negative_precision_p95": _safe_float(np.quantile(random_negative_precision, 0.95)),
    }


def selected_event_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "year",
        "products",
        "dominant_direction",
        "event_count",
        "volume_cut",
        "avg_gate_weight",
        "avg_max_corr",
        "avg_active_count",
        "avg_rsi",
        "breakout_rate",
        "avg_range_zscore",
        "avg_ret20_zscore",
        "avg_loss_streak",
        "trend_expansion_warning_score",
        "trend_expansion_warning_label",
        "target_negative20",
        "target_extreme_negative20",
        OUTCOME_METRIC,
        "fwd40d_delta_net_pnl_after_event",
    ]
    return df[columns].copy()


def build_report(
    summary: dict[str, Any],
    by_year_df: pd.DataFrame,
    by_score_df: pd.DataFrame,
    year_removal_df: pd.DataFrame,
    events_df: pd.DataFrame,
) -> str:
    severe_df = events_df[events_df["trend_expansion_warning_label"] == "severe_watch"].copy()
    worst_df = events_df.sort_values(OUTCOME_METRIC, ascending=True).head(12)
    lines = [
        "# 极端误伤/趋势扩散告警验证",
        "",
        "## 结论",
        "",
        f"- severe_watch 样本数：`{summary['severe_watch_count']}` / `{summary['date_count']}`",
        f"- extreme_negative 阈值：`{EXTREME_NEGATIVE_THRESHOLD:.0f}`",
        f"- severe_watch 极端负样本 precision：`{summary['extreme_negative_summary']['precision']:.4f}`",
        f"- severe_watch 对极端负样本 recall：`{summary['extreme_negative_summary']['recall']:.4f}`",
        f"- severe_watch 20日均值差：`{summary['negative_summary']['mean_fwd20_diff_severe_minus_non']:.2f}`",
        f"- 随机置换 p 值：`{summary['permutation_summary']['p_value_random_diff_le_observed']:.4f}`",
        "",
        "## 分年表现",
        "",
        to_markdown_table(by_year_df),
        "",
        "## 警戒分数表现",
        "",
        to_markdown_table(by_score_df),
        "",
        "## 剔除单年敏感性",
        "",
        to_markdown_table(year_removal_df),
        "",
        "## severe_watch事件",
        "",
        to_markdown_table(severe_df),
        "",
        "## 最差事件",
        "",
        to_markdown_table(worst_df),
        "",
        "## 使用边界",
        "",
        "- 这是告警验证，不是交易开关。",
        "- 样本数仍然太少，不允许直接写进仓位逻辑。",
        "- 若进入准实盘，只能作为人工复盘优先级和新增样本收集标签。",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = add_guardrail_targets(load_state())
    events_df = selected_event_columns(df)
    by_year_df = summarize_by_year(df)
    by_score_df = summarize_by_score(df)
    year_removal_df = build_year_removal(df)
    permutation_summary = run_permutation(df)
    negative_summary = summarize_alert(df, "target_negative20")
    extreme_negative_summary = summarize_alert(df, "target_extreme_negative20")

    summary = {
        "analysis": OUTPUT_PREFIX,
        "date_count": int(len(df)),
        "severe_watch_count": int(df["is_severe_watch"].sum()),
        "negative_threshold": NEGATIVE_THRESHOLD,
        "extreme_negative_threshold": EXTREME_NEGATIVE_THRESHOLD,
        "negative_summary": negative_summary,
        "extreme_negative_summary": extreme_negative_summary,
        "permutation_summary": permutation_summary,
        "by_year": by_year_df.to_dict(orient="records"),
        "by_score": by_score_df.to_dict(orient="records"),
        "year_removal": year_removal_df.to_dict(orient="records"),
        "model_judgement": {
            "first_principle": "小样本下不要训练黑箱模型；先验证固定告警是否能抓住真正危险的左尾事件。",
            "usage": "仅用于人工复盘优先级和准实盘新增样本标注，不作为自动关闭门控或调仓规则。",
        },
    }

    events_df.to_csv(EVENTS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_year_df.to_csv(BY_YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    by_score_df.to_csv(BY_SCORE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    year_removal_df.to_csv(YEAR_REMOVAL_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    PERMUTATION_OUTPUT_PATH.write_text(json.dumps(permutation_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(
        build_report(summary, by_year_df, by_score_df, year_removal_df, events_df),
        encoding="utf-8",
    )

    print(f"[corr-crowding-extreme-guardrail] summary: {SUMMARY_OUTPUT_PATH}")
    print(f"[corr-crowding-extreme-guardrail] report: {REPORT_OUTPUT_PATH}")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
