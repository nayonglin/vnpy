from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

INPUT_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_date_state.csv"
)
OUTPUT_PREFIX: str = "qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor"

EVENTS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events.csv"
BY_LABEL_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_warning_label.csv"
BY_SCORE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_by_warning_score.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary.json"
REPORT_MD_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report.md"

OUTCOME_METRIC: str = "fwd20d_delta_net_pnl_after_event"


def load_state() -> pd.DataFrame:
    df = pd.read_csv(INPUT_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def add_warning_flags(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["flag_rsi_hot"] = result["avg_rsi"] >= 70.0
    result["flag_breakout_hot"] = result["breakout_rate"] >= 0.5
    result["flag_range_expanding"] = result["avg_range_zscore"] >= 0.0
    result["flag_ret20_hot"] = result["avg_ret20_zscore"] >= 0.25
    result["flag_active_crowded"] = result["avg_active_count"] >= 3.5
    result["flag_loss_streak_active"] = result["avg_loss_streak"] >= 1.0
    flag_columns = [
        "flag_rsi_hot",
        "flag_breakout_hot",
        "flag_range_expanding",
        "flag_ret20_hot",
        "flag_active_crowded",
        "flag_loss_streak_active",
    ]
    result["trend_expansion_warning_score"] = result[flag_columns].sum(axis=1).astype(int)
    result["trend_expansion_warning_label"] = np.select(
        [
            result["trend_expansion_warning_score"] >= 5,
            result["trend_expansion_warning_score"] >= 3,
        ],
        [
            "severe_watch",
            "medium_watch",
        ],
        default="normal_watch",
    )
    result["monitor_action"] = np.select(
        [
            result["trend_expansion_warning_label"] == "severe_watch",
            result["trend_expansion_warning_label"] == "medium_watch",
        ],
        [
            "仅升级观察，不自动关闭门控；重点复盘20日路径是否少吃趋势扩散",
            "保留门控，观察后续20日路径与趋势成熟度变化",
        ],
        default="正常记录门控触发与20日路径",
    )
    return result


def summarize_by(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    grouped = df.groupby(group_column, dropna=False).agg(
        date_count=("date", "size"),
        event_count=("event_count", "sum"),
        mean_fwd20=(OUTCOME_METRIC, "mean"),
        median_fwd20=(OUTCOME_METRIC, "median"),
        hit_rate_fwd20=(OUTCOME_METRIC, lambda values: float((values > 0).mean())),
        negative_date_count=(OUTCOME_METRIC, lambda values: int((values < 0).sum())),
        mean_fwd5=("fwd5d_delta_net_pnl_after_event", "mean"),
        median_fwd5=("fwd5d_delta_net_pnl_after_event", "median"),
        avg_rsi=("avg_rsi", "mean"),
        avg_breakout_rate=("breakout_rate", "mean"),
        avg_range_zscore=("avg_range_zscore", "mean"),
        avg_ret20_zscore=("avg_ret20_zscore", "mean"),
        avg_active_count=("avg_active_count", "mean"),
        avg_loss_streak=("avg_loss_streak", "mean"),
        avg_volume_cut=("volume_cut", "mean"),
    )
    grouped.reset_index(inplace=True)
    grouped.sort_values([group_column], inplace=True)
    grouped.reset_index(drop=True, inplace=True)
    return grouped


def selected_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "products",
        "dominant_direction",
        "signals",
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
        "floor_pre20_return_sum",
        "trend_expansion_warning_score",
        "trend_expansion_warning_label",
        "monitor_action",
        "fwd5d_delta_net_pnl_after_event",
        "fwd20d_delta_net_pnl_after_event",
        "outcome_group",
    ]
    return df[columns].copy()


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_无记录_"
    compact_df = df.copy()
    for column in compact_df.columns:
        if pd.api.types.is_float_dtype(compact_df[column]):
            compact_df[column] = compact_df[column].map(lambda value: f"{float(value):.4f}")
    headers = [str(column) for column in compact_df.columns]
    rows = compact_df.astype(str).to_numpy().tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_markdown_report(
    monitor_df: pd.DataFrame,
    by_label: pd.DataFrame,
    by_score: pd.DataFrame,
) -> str:
    severe_df = monitor_df[monitor_df["trend_expansion_warning_label"] == "severe_watch"].copy()
    worst_severe = severe_df.sort_values([OUTCOME_METRIC, "date"], ascending=[True, True]).head(12)
    recent_events = monitor_df.sort_values("date", ascending=False).head(20)
    lines: list[str] = [
        "# 相关性拥挤门控监控报表",
        "",
        "## 说明",
        "",
        "- 这是监控报表，不是交易开关。",
        "- `severe_watch` 只表示趋势扩散误伤风险较高，不代表应自动关闭门控。",
        "- 后续应重点跟踪触发后 20 个交易日相对路径。",
        "",
        "## 警戒标签表现",
        "",
        to_markdown_table(by_label),
        "",
        "## 警戒分数表现",
        "",
        to_markdown_table(by_score),
        "",
        "## severe_watch 负样本",
        "",
        to_markdown_table(selected_columns(worst_severe)),
        "",
        "## 最近触发事件",
        "",
        to_markdown_table(selected_columns(recent_events)),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monitor_df = add_warning_flags(load_state())
    by_label = summarize_by(monitor_df, "trend_expansion_warning_label")
    by_score = summarize_by(monitor_df, "trend_expansion_warning_score")

    selected_columns(monitor_df).to_csv(EVENTS_CSV_PATH, index=False, encoding="utf-8-sig")
    by_label.to_csv(BY_LABEL_CSV_PATH, index=False, encoding="utf-8-sig")
    by_score.to_csv(BY_SCORE_CSV_PATH, index=False, encoding="utf-8-sig")
    REPORT_MD_PATH.write_text(build_markdown_report(monitor_df, by_label, by_score), encoding="utf-8")

    severe_df = monitor_df[monitor_df["trend_expansion_warning_label"] == "severe_watch"].copy()
    non_severe_df = monitor_df[monitor_df["trend_expansion_warning_label"] != "severe_watch"].copy()
    summary_payload: dict[str, Any] = {
        "analysis": OUTPUT_PREFIX,
        "input_path": str(INPUT_PATH),
        "date_count": int(len(monitor_df)),
        "severe_watch_date_count": int(len(severe_df)),
        "non_severe_date_count": int(len(non_severe_df)),
        "severe_watch_mean_fwd20": float(severe_df[OUTCOME_METRIC].mean()) if len(severe_df) else 0.0,
        "severe_watch_median_fwd20": float(severe_df[OUTCOME_METRIC].median()) if len(severe_df) else 0.0,
        "severe_watch_hit_rate_fwd20": float((severe_df[OUTCOME_METRIC] > 0).mean()) if len(severe_df) else 0.0,
        "severe_watch_negative_date_count": int((severe_df[OUTCOME_METRIC] < 0).sum()) if len(severe_df) else 0,
        "non_severe_mean_fwd20": float(non_severe_df[OUTCOME_METRIC].mean()) if len(non_severe_df) else 0.0,
        "non_severe_median_fwd20": float(non_severe_df[OUTCOME_METRIC].median()) if len(non_severe_df) else 0.0,
        "non_severe_hit_rate_fwd20": float((non_severe_df[OUTCOME_METRIC] > 0).mean()) if len(non_severe_df) else 0.0,
        "warning_label_summary": by_label.to_dict(orient="records"),
        "warning_score_summary": by_score.to_dict(orient="records"),
        "severe_watch_events": selected_columns(severe_df).to_dict(orient="records"),
        "latest_events": selected_columns(monitor_df.sort_values("date", ascending=False).head(20)).to_dict(
            orient="records"
        ),
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"summary json: {SUMMARY_JSON_PATH}")
    print(f"events csv: {EVENTS_CSV_PATH}")
    print(f"report md: {REPORT_MD_PATH}")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str))
    print("\n[by label]")
    print(by_label.to_string(index=False))
    print("\n[by score]")
    print(by_score.to_string(index=False))


if __name__ == "__main__":
    main()
