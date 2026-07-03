from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage031"
MODEL_TAG = "stage031_stage029_execution_lag_recovery_signal_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage031_stage029_execution_lag_recovery_signal_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage031_stage029_execution_lag_recovery_signal_audit"
STAGE_RECORD_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = PROJECT_DIR / "back_log.md"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE030_OUTPUT_DIR = LINE_DIR / "outputs" / "stage030_stage029_failure_attribution"
STAGE030_PREFIX = "rebuilt_c9_stage030_stage029_failure_attribution"
STAGE030_TAG = "stage030_stage029_failure_attribution_v1"

BASE_CLOSED_LOTS_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_closed_lots_{STAGE006_TAG}.csv"
STAGE030_EVENTS_PATH = STAGE030_OUTPUT_DIR / f"{STAGE030_PREFIX}_event_lot_attribution_{STAGE030_TAG}.csv"
STAGE030_DECISION_PATH = STAGE030_OUTPUT_DIR / f"{STAGE030_PREFIX}_decision_{STAGE030_TAG}.json"

LAGGED_EVENT_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lagged_event_lots_{MODEL_TAG}.csv"
TRIGGER_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_summary_{MODEL_TAG}.csv"
CANDIDATE_RANK_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_ai_rank_summary_{MODEL_TAG}.csv"
LOT_RANK_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_ai_rank_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
MONTH_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_lag_recovery_chart_{MODEL_TAG}.png"

MAX_MATCH_LAG_DAYS = 7

EXTERNAL_RESEARCH_JUDGMENT = (
    "Backtesting and look-ahead-bias references emphasize separating signal dates from execution dates. "
    "For this C9 event-driven engine, Stage031 therefore matches Stage029 skipped signal/candidate dates to "
    "Stage006 closed lots over the next 0-7 calendar days, rather than requiring same-day fills. This is a "
    "read-only attribution step, not a tradable filter."
)
OVERFIT_REFLECTION_BEFORE = (
    "否。Stage031 只修正 Stage030 的信号日/成交日匹配口径，不生成新交易规则，不按产品、日期或结果选择阈值。"
)
CONTINUE_VALUE_BEFORE = (
    "有。Stage030 已显示暂停事件大多是 Stage006 会开的候选，但必须确认这些候选后续真实 lot 是右尾还是亏损。"
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    return shown.to_markdown(index=False)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _rank_bucket(series: pd.Series) -> pd.Series:
    rank = pd.to_numeric(series, errors="coerce")
    return pd.Series(
        np.select(
            [
                rank.between(1, 3, inclusive="both"),
                rank.between(4, 6, inclusive="both"),
                rank.between(7, 9, inclusive="both"),
                rank.gt(9),
            ],
            ["rank_1_3", "rank_4_6", "rank_7_9", "rank_gt9"],
            default="missing",
        ),
        index=series.index,
    )


def _prepare_events() -> pd.DataFrame:
    events = _read_csv(STAGE030_EVENTS_PATH, low_memory=False)
    events = events.copy()
    events["requested_start_month"] = events["requested_start_month"].astype(str)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events["product_vt_symbol"] = events["product_vt_symbol"].astype(str)
    events["direction"] = events["direction"].astype(str).str.lower()
    events["event_month"] = events["date"].dt.strftime("%Y-%m")
    events["baseline_candidate_opened"] = pd.to_numeric(
        events.get("baseline_candidate_opened"), errors="coerce"
    ).fillna(0).astype(int)
    events["baseline_candidate_matched"] = pd.to_numeric(
        events.get("baseline_candidate_matched"), errors="coerce"
    ).fillna(0).astype(int)
    events["baseline_selected_volume_sum"] = pd.to_numeric(
        events.get("baseline_selected_volume_sum"), errors="coerce"
    ).fillna(0.0)
    events["stage029_injury_pause_reduced_volume"] = pd.to_numeric(
        events.get("stage029_injury_pause_reduced_volume"), errors="coerce"
    ).fillna(0.0)
    rank = events.get("baseline_candidate_min_ai_rank")
    if rank is None:
        rank = events.get("baseline_min_ai_rank", pd.Series(index=events.index, dtype=float))
    events["candidate_ai_rank_bucket"] = _rank_bucket(rank)
    events["event_key"] = (
        events["requested_start_month"]
        + "|"
        + events["date"].dt.strftime("%Y-%m-%d")
        + "|"
        + events["product_vt_symbol"]
        + "|"
        + events["direction"]
    )
    return events.dropna(subset=["date"]).reset_index(drop=True)


def _prepare_lots() -> pd.DataFrame:
    lots = _read_csv(BASE_CLOSED_LOTS_PATH, low_memory=False)
    lots = lots.copy()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["product_vt_symbol"] = lots["product"].astype(str)
    lots["direction"] = lots["direction"].astype(str).str.lower()
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    lots["volume"] = pd.to_numeric(lots["volume"], errors="coerce").fillna(0.0)
    lots["r_multiple"] = pd.to_numeric(lots["r_multiple"], errors="coerce")
    lots["winner"] = pd.to_numeric(lots.get("winner", 0), errors="coerce").fillna(0).astype(int)
    lots["big_winner"] = pd.to_numeric(lots.get("big_winner", 0), errors="coerce").fillna(0).astype(int)
    lots["ai_rank_bucket"] = lots.get("ai_rank_bucket", pd.Series(["missing"] * len(lots))).astype(str)
    lots["entry_context"] = lots.get("entry_context", pd.Series([""] * len(lots))).astype(str)
    return lots.dropna(subset=["entry_date"]).reset_index(drop=True)


def _lagged_match(events: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    opened = events[events["baseline_candidate_opened"].eq(1)].copy()
    event_cols = [
        "event_key",
        "requested_start_month",
        "date",
        "event_month",
        "product_vt_symbol",
        "direction",
        "trigger_bucket",
        "candidate_ai_rank_bucket",
        "baseline_candidate_matched",
        "baseline_candidate_opened",
        "baseline_selected_volume_sum",
        "stage029_injury_pause_reduced_volume",
    ]
    lot_cols = [
        "requested_start_month",
        "entry_date",
        "exit_date",
        "product_vt_symbol",
        "direction",
        "lot_id",
        "vt_symbol",
        "volume",
        "realized_pnl",
        "r_multiple",
        "winner",
        "big_winner",
        "ai_rank_bucket",
        "risk_multiplier_bucket",
        "entry_context",
        "signal",
    ]
    merged = opened[event_cols].merge(
        lots[lot_cols],
        on=["requested_start_month", "product_vt_symbol", "direction"],
        how="left",
    )
    merged["match_lag_days"] = (merged["entry_date"] - merged["date"]).dt.days
    merged = merged[
        merged["match_lag_days"].ge(0)
        & merged["match_lag_days"].le(MAX_MATCH_LAG_DAYS)
        & merged["entry_context"].eq("flat_entry")
    ].copy()
    if merged.empty:
        return merged
    min_lag = merged.groupby("event_key")["match_lag_days"].transform("min")
    matched = merged[merged["match_lag_days"].eq(min_lag)].copy()
    matched["lag_bucket"] = pd.cut(
        matched["match_lag_days"],
        bins=[-0.1, 0, 1, 3, 7],
        labels=["same_day", "next_day", "lag_2_3d", "lag_4_7d"],
    ).astype(str)
    return matched.reset_index(drop=True)


def _event_level(matched: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    agg = (
        matched.groupby("event_key", as_index=False)
        .agg(
            requested_start_month=("requested_start_month", "first"),
            event_date=("date", "first"),
            event_month=("event_month", "first"),
            product_vt_symbol=("product_vt_symbol", "first"),
            direction=("direction", "first"),
            trigger_bucket=("trigger_bucket", "first"),
            candidate_ai_rank_bucket=("candidate_ai_rank_bucket", "first"),
            stage006_entry_date=("entry_date", "min"),
            match_lag_days=("match_lag_days", "min"),
            stage006_lot_count=("lot_id", "count"),
            stage006_volume=("volume", "sum"),
            stage006_realized_pnl=("realized_pnl", "sum"),
            stage006_mean_r_multiple=("r_multiple", "mean"),
            stage006_winner_lot_count=("winner", "sum"),
            stage006_big_winner_lot_count=("big_winner", "sum"),
            stage006_lot_ai_rank_bucket=("ai_rank_bucket", lambda s: "|".join(sorted(set(map(str, s.dropna())))[:4])),
            baseline_selected_volume_sum=("baseline_selected_volume_sum", "first"),
            stage029_reduced_volume=("stage029_injury_pause_reduced_volume", "first"),
        )
    )
    agg["stage006_event_pnl_positive"] = agg["stage006_realized_pnl"].gt(0).astype(int)
    agg["stage006_event_pnl_negative"] = agg["stage006_realized_pnl"].lt(0).astype(int)
    agg["stage006_event_big_winner"] = agg["stage006_big_winner_lot_count"].gt(0).astype(int)

    opened_events = events[events["baseline_candidate_opened"].eq(1)][
        [
            "event_key",
            "requested_start_month",
            "date",
            "event_month",
            "product_vt_symbol",
            "direction",
            "trigger_bucket",
            "candidate_ai_rank_bucket",
            "baseline_selected_volume_sum",
            "stage029_injury_pause_reduced_volume",
        ]
    ].copy()
    full = opened_events.merge(agg, on="event_key", how="left", suffixes=("", "_matched"))
    full["lagged_lot_matched"] = full["stage006_lot_count"].notna().astype(int)
    for column in [
        "stage006_lot_count",
        "stage006_volume",
        "stage006_realized_pnl",
        "stage006_mean_r_multiple",
        "stage006_winner_lot_count",
        "stage006_big_winner_lot_count",
        "stage006_event_pnl_positive",
        "stage006_event_pnl_negative",
        "stage006_event_big_winner",
    ]:
        full[column] = pd.to_numeric(full[column], errors="coerce").fillna(0.0)
    return full


def _summary(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    grouped = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            opened_pause_event_count=("event_key", "count"),
            lagged_lot_matched_count=("lagged_lot_matched", "sum"),
            baseline_selected_volume_sum=("baseline_selected_volume_sum", "sum"),
            stage029_reduced_volume_sum=("stage029_injury_pause_reduced_volume", "sum"),
            stage006_volume_sum=("stage006_volume", "sum"),
            stage006_realized_pnl=("stage006_realized_pnl", "sum"),
            positive_event_count=("stage006_event_pnl_positive", "sum"),
            negative_event_count=("stage006_event_pnl_negative", "sum"),
            big_winner_event_count=("stage006_event_big_winner", "sum"),
            avg_match_lag_days=("match_lag_days", "mean"),
            avg_r_multiple=("stage006_mean_r_multiple", "mean"),
        )
        .reset_index()
    )
    grouped["lagged_match_rate_pct"] = np.where(
        grouped["opened_pause_event_count"] > 0,
        grouped["lagged_lot_matched_count"] / grouped["opened_pause_event_count"] * 100.0,
        np.nan,
    )
    grouped["positive_event_rate_pct"] = np.where(
        grouped["lagged_lot_matched_count"] > 0,
        grouped["positive_event_count"] / grouped["lagged_lot_matched_count"] * 100.0,
        np.nan,
    )
    return grouped


def _plot(trigger: pd.DataFrame, rank: pd.DataFrame, product: pd.DataFrame, month: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)

    ax = axes[0, 0]
    trigger_plot = trigger.sort_values("stage006_realized_pnl")
    ax.barh(trigger_plot["trigger_bucket"], trigger_plot["stage006_realized_pnl"], color="#f97316")
    ax.set_title("Lagged Stage006 PnL By Stage029 Trigger")
    ax.set_xlabel("realized pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[0, 1]
    order = ["rank_1_3", "rank_4_6", "rank_7_9", "rank_gt9", "missing"]
    rank_plot = rank.set_index("candidate_ai_rank_bucket").reindex(order).dropna(how="all").reset_index()
    ax.bar(rank_plot["candidate_ai_rank_bucket"], rank_plot["stage006_realized_pnl"], color="#2563eb")
    ax.set_title("Lagged Stage006 PnL By Candidate AI Rank Bucket")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    product_plot = product.sort_values("stage006_realized_pnl", ascending=False).head(15)
    labels = product_plot["product_vt_symbol"].astype(str) + " " + product_plot["direction"].astype(str)
    ax.barh(labels[::-1], product_plot["stage006_realized_pnl"][::-1], color="#16a34a")
    ax.set_title("Top Positive Lagged PnL By Product Direction")
    ax.set_xlabel("realized pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1, 1]
    month_plot = month.sort_values("event_month").tail(42)
    ax.bar(month_plot["event_month"], month_plot["stage006_realized_pnl"], color="#64748b")
    ax.set_title("Lagged Stage006 PnL By Event Month")
    ax.tick_params(axis="x", rotation=60, labelsize=7)
    ax.grid(True, axis="y", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(event_level: pd.DataFrame, trigger: pd.DataFrame, rank: pd.DataFrame) -> dict[str, Any]:
    opened_count = int(len(event_level))
    matched_count = int(pd.to_numeric(event_level["lagged_lot_matched"], errors="coerce").fillna(0).sum())
    total_pnl = float(pd.to_numeric(event_level["stage006_realized_pnl"], errors="coerce").fillna(0.0).sum())
    positive_count = int(pd.to_numeric(event_level["stage006_event_pnl_positive"], errors="coerce").fillna(0).sum())
    negative_count = int(pd.to_numeric(event_level["stage006_event_pnl_negative"], errors="coerce").fillna(0).sum())
    loss_streak = trigger[trigger["trigger_bucket"].eq("loss_streak_only")]
    rank_good = rank[rank["candidate_ai_rank_bucket"].isin(["rank_1_3", "rank_4_6", "rank_7_9"])]
    rank_gt9 = rank[rank["candidate_ai_rank_bucket"].eq("rank_gt9")]

    conclusion = (
        "Stage031 修正信号日/成交日错位后，Stage029 暂停掉的 Stage006 实际开仓集合呈现强正贡献。"
        "尤其 loss_streak_only 不是坏集合，而是主要右尾来源；AI rank 1-9 桶整体为正，rank_gt9 偏负。"
        "这提示后续若继续交易层研究，应是“高质量恢复机会豁免/加风险”的只读验证，而不是账户受伤后机械暂停。"
    )
    decision = "stage031_read_only_recovery_signal_audit_complete_no_candidate"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "conclusion": conclusion,
        "max_match_lag_days": MAX_MATCH_LAG_DAYS,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": OVERFIT_REFLECTION_BEFORE,
        "continue_value_before": CONTINUE_VALUE_BEFORE,
        "overfit_reflection_after": (
            "否。本阶段只修正归因口径并输出只读证据；如果直接按 lc/SM/si 或单年月份写豁免规则，会变成过拟合。"
        ),
        "continue_value_after": (
            "有。下一步值得验证一个极低自由度的高质量恢复标签，但必须跨 source、跨年份、跨产品成立；"
            "否则应转非交易账户层资金安排。"
        ),
        "metrics": {
            "opened_pause_event_count": opened_count,
            "lagged_lot_matched_event_count": matched_count,
            "lagged_match_rate_pct": float(matched_count / opened_count * 100.0) if opened_count else 0.0,
            "stage006_lagged_realized_pnl": total_pnl,
            "positive_event_count": positive_count,
            "negative_event_count": negative_count,
            "loss_streak_only_event_count": int(loss_streak["opened_pause_event_count"].sum()) if not loss_streak.empty else 0,
            "loss_streak_only_lagged_pnl": float(loss_streak["stage006_realized_pnl"].sum()) if not loss_streak.empty else 0.0,
            "rank_1_to_9_lagged_pnl": float(rank_good["stage006_realized_pnl"].sum()) if not rank_good.empty else 0.0,
            "rank_gt9_lagged_pnl": float(rank_gt9["stage006_realized_pnl"].sum()) if not rank_gt9.empty else 0.0,
        },
        "outputs": {
            "lagged_event_lots": str(LAGGED_EVENT_LOTS_PATH),
            "trigger_summary": str(TRIGGER_SUMMARY_PATH),
            "candidate_ai_rank_summary": str(CANDIDATE_RANK_SUMMARY_PATH),
            "lot_ai_rank_summary": str(LOT_RANK_SUMMARY_PATH),
            "product_direction_summary": str(PRODUCT_DIRECTION_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "month_summary": str(MONTH_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    trigger: pd.DataFrame,
    candidate_rank: pd.DataFrame,
    lot_rank: pd.DataFrame,
    product: pd.DataFrame,
    source: pd.DataFrame,
    month: pd.DataFrame,
) -> None:
    metrics = decision["metrics"]
    lines = [
        "# Stage031 Stage029 信号日-成交日滞后匹配归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读归因；不生成新候选、不改官方 live config、不连接 CTP、不调用下单。",
        f"- 滞后匹配窗口：`0-{MAX_MATCH_LAG_DAYS}` 自然日。",
        "",
        "## 外部调研判断",
        "",
        f"- {EXTERNAL_RESEARCH_JUDGMENT}",
        "",
        "## 核心结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 结论：{decision['conclusion']}",
        f"- Stage006 实际打开的 Stage029 暂停事件：`{metrics['opened_pause_event_count']}`。",
        f"- 可匹配到后续 closed-lot 的事件：`{metrics['lagged_lot_matched_event_count']}`，匹配率 `{metrics['lagged_match_rate_pct']:.4f}%`。",
        f"- Stage006 滞后匹配 realized PnL：`{metrics['stage006_lagged_realized_pnl']:.2f}`。",
        f"- 正/负事件：`{metrics['positive_event_count']}` / `{metrics['negative_event_count']}`。",
        f"- loss_streak_only 事件/PNL：`{metrics['loss_streak_only_event_count']}` / `{metrics['loss_streak_only_lagged_pnl']:.2f}`。",
        f"- candidate AI rank 1-9 PNL：`{metrics['rank_1_to_9_lagged_pnl']:.2f}`；rank>9 PNL：`{metrics['rank_gt9_lagged_pnl']:.2f}`。",
        "",
        "## Trigger 归因",
        "",
        _md_table(trigger, max_rows=20),
        "",
        "## 候选 AI rank 归因",
        "",
        _md_table(candidate_rank, max_rows=20),
        "",
        "## Lot AI rank 归因",
        "",
        _md_table(lot_rank, max_rows=20),
        "",
        "## 产品方向 Top20",
        "",
        _md_table(product.sort_values("stage006_realized_pnl", ascending=False).head(20), max_rows=20),
        "",
        "## Source 归因",
        "",
        _md_table(source.sort_values("stage006_realized_pnl", ascending=False), max_rows=20),
        "",
        "## 月份 Top20",
        "",
        _md_table(month.sort_values("stage006_realized_pnl", ascending=False).head(20), max_rows=20),
        "",
        "## 判断",
        "",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    metrics = decision["metrics"]
    path = STAGE_RECORD_DIR / "20260701_1716_stage031_stage029_execution_lag_recovery_signal_audit.md"
    lines = [
        "# Stage031 - Stage029 信号日/成交日滞后匹配归因",
        "",
        f"- 时间：`{decision['generated_at']}`",
        "- 是否重要突破版本：否；这是只读归因，不是候选策略。",
        "- 新增参数：无。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "- 新增回测结果：无新增真实回测；复用 Stage006/Stage030 产物做滞后匹配归因。",
        "- 修改回测结果：无。",
        "- 删除回测结果：无。",
        f"- Stage006 实际打开的暂停事件：`{metrics['opened_pause_event_count']}`。",
        f"- 滞后 closed-lot 匹配事件：`{metrics['lagged_lot_matched_event_count']}`，匹配率 `{metrics['lagged_match_rate_pct']:.4f}%`。",
        f"- Stage006 滞后匹配 realized PnL：`{metrics['stage006_lagged_realized_pnl']:.2f}`。",
        f"- loss_streak_only 事件/PNL：`{metrics['loss_streak_only_event_count']}` / `{metrics['loss_streak_only_lagged_pnl']:.2f}`。",
        f"- candidate AI rank 1-9 PNL：`{metrics['rank_1_to_9_lagged_pnl']:.2f}`；rank>9 PNL：`{metrics['rank_gt9_lagged_pnl']:.2f}`。",
        "- 胜率：不新增策略胜率；使用滞后 matched event 正负 PnL 事件。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "- 后续规划：可做一个预声明、低自由度的高质量恢复标签只读验证；不得按产品/日期/年份硬编码。",
        "",
        "## 输出",
        "",
        f"- 报告：`{REPORT_PATH}`",
        f"- 决策：`{DECISION_PATH}`",
        f"- 图表：`{CHART_PATH}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _append_back_log(decision: dict[str, Any], stage_record: Path) -> None:
    marker = "`futures_trend_rebuilt_c9_15w_optimization` Stage031"
    if BACK_LOG_PATH.exists() and marker in BACK_LOG_PATH.read_text(encoding="utf-8"):
        return
    metrics = decision["metrics"]
    line = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage031 完成 Stage029 信号日/成交日滞后匹配归因，"
        f"决策 `{decision['decision']}`。本阶段只读复用 Stage006/Stage030 产物，不改正式配置、不连接 CTP、不调用订单 API。"
        f"Stage006 实际打开的暂停事件 `{metrics['opened_pause_event_count']}`，0-{MAX_MATCH_LAG_DAYS}日内匹配 closed-lot "
        f"`{metrics['lagged_lot_matched_event_count']}`，匹配率 `{metrics['lagged_match_rate_pct']:.4f}%`，"
        f"Stage006 滞后 realized PnL `{metrics['stage006_lagged_realized_pnl']:.2f}`，"
        f"loss_streak_only PnL `{metrics['loss_streak_only_lagged_pnl']:.2f}`，candidate AI rank 1-9 PnL "
        f"`{metrics['rank_1_to_9_lagged_pnl']:.2f}`、rank>9 PnL `{metrics['rank_gt9_lagged_pnl']:.2f}`。"
        f"结论：Stage029 砍掉的是账户受伤后的大量恢复右尾，不应继续机械暂停；下一步仅允许预声明高质量恢复标签只读验证。"
        f"记录 `{stage_record}`，报告 `{REPORT_PATH}`。\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    events = _prepare_events()
    lots = _prepare_lots()
    lagged = _lagged_match(events, lots)
    event_level = _event_level(lagged, events)

    trigger = _summary(event_level, ["trigger_bucket"]).sort_values("stage006_realized_pnl", ascending=False)
    candidate_rank = _summary(event_level, ["candidate_ai_rank_bucket"]).sort_values("stage006_realized_pnl", ascending=False)
    lot_rank = _summary(event_level, ["stage006_lot_ai_rank_bucket"]).sort_values("stage006_realized_pnl", ascending=False)
    product = _summary(event_level, ["product_vt_symbol", "direction"]).sort_values("stage006_realized_pnl", ascending=False)
    source = _summary(event_level, ["requested_start_month"]).sort_values("stage006_realized_pnl", ascending=False)
    month = _summary(event_level, ["event_month"]).sort_values("event_month")

    event_level.to_csv(LAGGED_EVENT_LOTS_PATH, index=False, encoding="utf-8-sig")
    trigger.to_csv(TRIGGER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_rank.to_csv(CANDIDATE_RANK_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    lot_rank.to_csv(LOT_RANK_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    month.to_csv(MONTH_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    _plot(trigger, candidate_rank, product, month)
    decision = _decision(event_level, trigger, candidate_rank)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, trigger, candidate_rank, lot_rank, product, source, month)
    stage_record = _write_stage_record(decision)
    _append_back_log(decision, stage_record)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
